package com.blueradar.app.service

import android.app.*
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.bluetooth.le.*
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import com.blueradar.app.MainActivity
import com.blueradar.app.R
import com.blueradar.app.model.BluetoothDeviceInfo
import com.blueradar.app.model.DeviceType
import com.blueradar.app.model.ProximityLevel
import com.blueradar.app.util.ManufacturerParser
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.concurrent.ConcurrentHashMap

class BluetoothRadarService : Service() {

    companion object {
        const val CHANNEL_ID = "blueradar_scan_channel"
        const val ALERT_CHANNEL_ID = "blueradar_alert_channel"
        const val NOTIFICATION_ID = 1001
        const val ACTION_START = "com.blueradar.app.START_SCAN"
        const val ACTION_STOP = "com.blueradar.app.STOP_SCAN"

        private val _devices = MutableStateFlow<Map<String, BluetoothDeviceInfo>>(emptyMap())
        val devices: StateFlow<Map<String, BluetoothDeviceInfo>> = _devices.asStateFlow()

        private val _isScanning = MutableStateFlow(false)
        val isScanning: StateFlow<Boolean> = _isScanning.asStateFlow()

        private val _scanStats = MutableStateFlow(ScanStats())
        val scanStats: StateFlow<ScanStats> = _scanStats.asStateFlow()

        const val MIN_RSSI_THRESHOLD = -120
        const val WARNING_DISTANCE_METERS = 10.0
    }

    data class ScanStats(
        val totalSeen: Int = 0,
        val currentlyVisible: Int = 0,
        val inWarningRange: Int = 0,
        val scanUptimeMs: Long = 0
    )

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var bluetoothAdapter: BluetoothAdapter? = null
    private var bleScanner: BluetoothLeScanner? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private var scanStartTime = 0L
    private val deviceMap = ConcurrentHashMap<String, BluetoothDeviceInfo>()
    private val recentlyAlerted = ConcurrentHashMap<String, Long>()
    private val ALERT_COOLDOWN_MS = 45_000L

    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) { handleScanResult(result) }
        override fun onBatchScanResults(results: MutableList<ScanResult>) { results.forEach { handleScanResult(it) } }
        override fun onScanFailed(errorCode: Int) {
            serviceScope.launch {
                delay(2000)
                if (_isScanning.value) startBleScan(aggressive = true)
            }
        }
    }

    private val classicReceiver = object : android.content.BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            when (intent?.action) {
                BluetoothDevice.ACTION_FOUND -> {
                    val device: BluetoothDevice? =
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU)
                            intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice::class.java)
                        else @Suppress("DEPRECATION") intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
                    val rssi = intent.getShortExtra(BluetoothDevice.EXTRA_RSSI, Short.MIN_VALUE).toInt()
                    if (device != null && rssi > MIN_RSSI_THRESHOLD) handleClassicDevice(device, rssi)
                }
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
        val btManager = getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
        bluetoothAdapter = btManager.adapter
        bleScanner = bluetoothAdapter?.bluetoothLeScanner
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "BlueRadar::ScanWakeLock")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> startScanning()
            ACTION_STOP -> stopScanning()
            else -> startScanning()
        }
        return START_STICKY
    }

    private fun startScanning() {
        if (_isScanning.value) return
        _isScanning.value = true
        scanStartTime = System.currentTimeMillis()
        wakeLock?.acquire(10 * 60 * 60 * 1000L)

        val notification = buildOngoingNotification("Scanning for nearby Bluetooth signals...")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q)
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
        else startForeground(NOTIFICATION_ID, notification)

        startBleScan(aggressive = true)
        startClassicDiscovery()

        serviceScope.launch {
            while (_isScanning.value) {
                delay(12_000)
                try {
                    bluetoothAdapter?.cancelDiscovery()
                    delay(500)
                    bluetoothAdapter?.startDiscovery()
                } catch (_: Exception) {}
            }
        }

        serviceScope.launch {
            while (_isScanning.value) {
                cleanupStaleDevices()
                updateStats()
                delay(3000)
            }
        }
    }

    private fun startBleScan(aggressive: Boolean) {
        val scanner = bleScanner ?: return
        try { scanner.stopScan(scanCallback) } catch (_: Exception) {}

        val settings = ScanSettings.Builder()
            .setScanMode(if (aggressive) ScanSettings.SCAN_MODE_LOW_LATENCY else ScanSettings.SCAN_MODE_BALANCED)
            .setReportDelay(0)
            .setCallbackType(ScanSettings.CALLBACK_TYPE_ALL_MATCHES)
            .setMatchMode(ScanSettings.MATCH_MODE_AGGRESSIVE)
            .setNumOfMatches(ScanSettings.MATCH_NUM_MAX_ADVERTISEMENT)
            .build()

        scanner.startScan(null, settings, scanCallback)
    }

    private fun startClassicDiscovery() {
        val filter = android.content.IntentFilter(BluetoothDevice.ACTION_FOUND)
        try { registerReceiver(classicReceiver, filter) } catch (_: Exception) {}
        try { bluetoothAdapter?.startDiscovery() } catch (_: SecurityException) {}
    }

    private fun handleScanResult(result: ScanResult) {
        val device = result.device
        val rssi = result.rssi
        if (rssi < MIN_RSSI_THRESHOLD) return

        val address = device.address
        val name = try { device.name } catch (_: SecurityException) { null } ?: result.scanRecord?.deviceName

        val (manufacturer, typeFromMfg) = ManufacturerParser.parseManufacturer(result.scanRecord?.bytes)
        val typeFromName = ManufacturerParser.classifyByName(name)
        val finalType = when {
            typeFromMfg != DeviceType.UNKNOWN -> typeFromMfg
            typeFromName != DeviceType.UNKNOWN -> typeFromName
            else -> DeviceType.UNKNOWN
        }

        val txPower = result.scanRecord?.txPowerLevel?.takeIf { it != Int.MIN_VALUE }
        val distance = BluetoothDeviceInfo.estimateDistance(rssi, txPower ?: -59)
        val existing = deviceMap[address]
        val history = ((existing?.rssiHistory ?: emptyList()) + rssi).takeLast(40)

        val info = BluetoothDeviceInfo(
            address = address, name = name, rssi = rssi,
            estimatedDistanceMeters = distance,
            isConnectable = result.isConnectable,
            deviceType = finalType, manufacturer = manufacturer,
            isBle = true, txPower = txPower,
            firstSeen = existing?.firstSeen ?: System.currentTimeMillis(),
            lastSeen = System.currentTimeMillis(),
            rssiHistory = history,
            isInWarningRange = distance <= WARNING_DISTANCE_METERS,
            bondState = try { device.bondState } catch (_: SecurityException) { BluetoothDevice.BOND_NONE },
            rawScanRecord = result.scanRecord?.bytes
        )

        deviceMap[address] = info
        _devices.value = HashMap(deviceMap)
        if (info.isInWarningRange) maybeAlert(info)
    }

    private fun handleClassicDevice(device: BluetoothDevice, rssi: Int) {
        val address = device.address
        val name = try { device.name } catch (_: SecurityException) { null }
        val distance = BluetoothDeviceInfo.estimateDistance(rssi)
        val existing = deviceMap[address]

        val info = BluetoothDeviceInfo(
            address = address, name = name, rssi = rssi,
            estimatedDistanceMeters = distance, isBle = false,
            deviceType = ManufacturerParser.classifyByName(name),
            firstSeen = existing?.firstSeen ?: System.currentTimeMillis(),
            lastSeen = System.currentTimeMillis(),
            rssiHistory = ((existing?.rssiHistory ?: emptyList()) + rssi).takeLast(40),
            isInWarningRange = distance <= WARNING_DISTANCE_METERS,
            bondState = try { device.bondState } catch (_: SecurityException) { BluetoothDevice.BOND_NONE }
        )
        deviceMap[address] = info
        _devices.value = HashMap(deviceMap)
        if (info.isInWarningRange) maybeAlert(info)
    }

    private fun maybeAlert(info: BluetoothDeviceInfo) {
        val now = System.currentTimeMillis()
        if (now - (recentlyAlerted[info.address] ?: 0L) < ALERT_COOLDOWN_MS) return
        recentlyAlerted[info.address] = now

        val level = info.proximityLevel
        val title = when (level) {
            ProximityLevel.IMMEDIATE -> "VERY CLOSE - ${info.displayName}"
            ProximityLevel.NEAR -> "Nearby device - ${info.displayName}"
            else -> "Device in range - ${info.displayName}"
        }
        val body = buildString {
            append("%.1fm | RSSI %d dBm".format(info.estimatedDistanceMeters, info.rssi))
            info.manufacturer?.let { append(" | $it") }
            if (info.name.isNullOrBlank()) append(" | HIDDEN")
            append(" | ${info.deviceType.name.lowercase().replaceFirstChar { it.uppercase() }}")
        }

        val notification = NotificationCompat.Builder(this, ALERT_CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_radar)
            .setContentTitle(title)
            .setContentText(body)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setAutoCancel(true)
            .setVibrate(when (level) {
                ProximityLevel.IMMEDIATE -> longArrayOf(0, 400, 150, 400, 150, 400)
                ProximityLevel.NEAR -> longArrayOf(0, 250, 120, 250)
                else -> longArrayOf(0, 180)
            })
            .setContentIntent(PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE))
            .build()

        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(info.address.hashCode() and 0x7FFFFFFF, notification)
    }

    private fun cleanupStaleDevices() {
        val now = System.currentTimeMillis()
        val timeout = 90_000L
        val iterator = deviceMap.entries.iterator()
        while (iterator.hasNext()) {
            if (now - iterator.next().value.lastSeen > timeout) iterator.remove()
        }
        _devices.value = HashMap(deviceMap)
    }

    private fun updateStats() {
        val list = deviceMap.values
        _scanStats.value = ScanStats(
            totalSeen = list.size, currentlyVisible = list.size,
            inWarningRange = list.count { it.isInWarningRange },
            scanUptimeMs = System.currentTimeMillis() - scanStartTime
        )
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIFICATION_ID, buildOngoingNotification(
            "${list.size} devices | ${list.count { it.isInWarningRange }} in 10 m zone"
        ))
    }

    private fun stopScanning() {
        _isScanning.value = false
        try {
            bleScanner?.stopScan(scanCallback)
            bluetoothAdapter?.cancelDiscovery()
            unregisterReceiver(classicReceiver)
        } catch (_: Exception) {}
        wakeLock?.let { if (it.isHeld) it.release() }
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun createNotificationChannels() {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(NotificationChannel(CHANNEL_ID, "Bluetooth Radar Scanning", NotificationManager.IMPORTANCE_LOW).apply {
            description = "Ongoing scan status"; setShowBadge(false)
        })
        nm.createNotificationChannel(NotificationChannel(ALERT_CHANNEL_ID, "Proximity Alerts", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Warnings when devices enter the 10 m zone"
            enableVibration(true); vibrationPattern = longArrayOf(0, 300, 150, 300)
        })
    }

    private fun buildOngoingNotification(text: String): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("BlueRadar Active")
            .setContentText(text)
            .setSmallIcon(R.drawable.ic_radar)
            .setOngoing(true).setOnlyAlertOnce(true)
            .setContentIntent(PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE))
            .addAction(R.drawable.ic_stop, "Stop",
                PendingIntent.getService(this, 1,
                    Intent(this, BluetoothRadarService::class.java).setAction(ACTION_STOP),
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE))
            .build()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        stopScanning()
        serviceScope.cancel()
        super.onDestroy()
    }
}
