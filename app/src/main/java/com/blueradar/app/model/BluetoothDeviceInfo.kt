package com.blueradar.app.model

import android.bluetooth.BluetoothDevice
import android.os.Parcelable
import kotlinx.parcelize.Parcelize

@Parcelize
data class BluetoothDeviceInfo(
    val address: String,
    val name: String?,
    val rssi: Int,
    val estimatedDistanceMeters: Double,
    val isConnectable: Boolean = false,
    val deviceType: DeviceType = DeviceType.UNKNOWN,
    val manufacturer: String? = null,
    val isBle: Boolean = true,
    val txPower: Int? = null,
    val firstSeen: Long = System.currentTimeMillis(),
    val lastSeen: Long = System.currentTimeMillis(),
    val rssiHistory: List<Int> = emptyList(),
    val isInWarningRange: Boolean = false,
    val bondState: Int = BluetoothDevice.BOND_NONE
) : Parcelable {

    val displayName: String
        get() = name?.takeIf { it.isNotBlank() } ?: "Unknown Device"

    val signalStrengthPercent: Int
        get() = when {
            rssi >= -50 -> 100
            rssi >= -60 -> 85
            rssi >= -70 -> 70
            rssi >= -80 -> 50
            rssi >= -90 -> 30
            else -> 15
        }.coerceIn(0, 100)

    val proximityLevel: ProximityLevel
        get() = when {
            estimatedDistanceMeters <= 1.5 -> ProximityLevel.IMMEDIATE
            estimatedDistanceMeters <= 4.0 -> ProximityLevel.NEAR
            estimatedDistanceMeters <= 10.0 -> ProximityLevel.MEDIUM
            else -> ProximityLevel.FAR
        }

    companion object {
        fun estimateDistance(rssi: Int, txPower: Int = -59, pathLossExponent: Double = 2.2): Double {
            if (rssi == 0) return -1.0
            val ratio = (txPower - rssi) / (10.0 * pathLossExponent)
            return Math.pow(10.0, ratio).coerceAtMost(100.0)
        }
    }
}

enum class DeviceType {
    PHONE, HEADSET, SPEAKER, TRACKER, WEARABLE, COMPUTER, KEYBOARD_MOUSE, UNKNOWN
}

enum class ProximityLevel {
    IMMEDIATE, NEAR, MEDIUM, FAR
}
