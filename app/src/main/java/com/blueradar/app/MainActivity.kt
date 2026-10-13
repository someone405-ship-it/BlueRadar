package com.blueradar.app

import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.core.view.WindowCompat
import com.blueradar.app.service.BluetoothRadarService
import com.blueradar.app.ui.screens.RadarScreen
import com.blueradar.app.ui.theme.BlueRadarTheme
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.rememberMultiplePermissionsState

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        WindowCompat.setDecorFitsSystemWindows(window, false)

        setContent {
            BlueRadarTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    BlueRadarAppContent(
                        onStartService = { startRadarService() },
                        onStopService = { stopRadarService() }
                    )
                }
            }
        }
    }

    private fun startRadarService() {
        val intent = Intent(this, BluetoothRadarService::class.java).apply {
            action = BluetoothRadarService.ACTION_START
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
    }

    private fun stopRadarService() {
        val intent = Intent(this, BluetoothRadarService::class.java).apply {
            action = BluetoothRadarService.ACTION_STOP
        }
        startService(intent)
    }
}

@OptIn(ExperimentalPermissionsApi::class)
@Composable
fun BlueRadarAppContent(
    onStartService: () -> Unit,
    onStopService: () -> Unit
) {
    val permissions = buildList {
        add(Manifest.permission.ACCESS_FINE_LOCATION)
        add(Manifest.permission.ACCESS_COARSE_LOCATION)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            add(Manifest.permission.BLUETOOTH_SCAN)
            add(Manifest.permission.BLUETOOTH_CONNECT)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            add(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    val permissionState = rememberMultiplePermissionsState(permissions)

    RadarScreen(
        permissionState = permissionState,
        onStartScan = onStartService,
        onStopScan = onStopService
    )
}
