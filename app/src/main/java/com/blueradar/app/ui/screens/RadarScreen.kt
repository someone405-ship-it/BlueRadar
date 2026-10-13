package com.blueradar.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material.icons.outlined.BluetoothSearching
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.blueradar.app.service.BluetoothRadarService
import com.blueradar.app.ui.components.DeviceCard
import com.blueradar.app.ui.components.RadarCanvas
import com.blueradar.app.ui.theme.*
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.MultiplePermissionsState
import kotlinx.coroutines.delay

@OptIn(ExperimentalPermissionsApi::class, ExperimentalMaterial3Api::class)
@Composable
fun RadarScreen(
    permissionState: MultiplePermissionsState,
    onStartScan: () -> Unit,
    onStopScan: () -> Unit
) {
    val devicesMap by BluetoothRadarService.devices.collectAsState()
    val isScanning by BluetoothRadarService.isScanning.collectAsState()
    val stats by BluetoothRadarService.scanStats.collectAsState()

    val devices = remember(devicesMap) {
        devicesMap.values.sortedWith(
            compareBy({ it.estimatedDistanceMeters }, { -it.rssi })
        ).toList()
    }

    LaunchedEffect(Unit) {
        if (!permissionState.allPermissionsGranted) {
            delay(400)
            permissionState.launchMultiplePermissionRequest()
        }
    }

    Scaffold(
        containerColor = DeepSpace,
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            "BlueRadar",
                            fontWeight = FontWeight.Bold,
                            color = NeonCyan,
                            fontSize = 22.sp
                        )
                        Spacer(Modifier.width(8.dp))
                        if (isScanning) {
                            Box(
                                modifier = Modifier
                                    .size(8.dp)
                                    .clip(CircleShape)
                                    .background(NeonGreen)
                            )
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color.Transparent
                ),
                actions = {
                    IconButton(onClick = { }) {
                        Icon(
                            Icons.Default.Settings,
                            contentDescription = "Settings",
                            tint = SoftWhite.copy(alpha = 0.7f)
                        )
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(
                    Brush.verticalGradient(listOf(DeepSpace, Color(0xFF080818)))
                )
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                StatChip("Visible", stats.currentlyVisible.toString(), NeonCyan)
                StatChip(
                    "In 10 m",
                    stats.inWarningRange.toString(),
                    if (stats.inWarningRange > 0) WarningRed else NeonGreen
                )
                StatChip(
                    "Uptime",
                    formatUptime(stats.scanUptimeMs),
                    SoftWhite.copy(alpha = 0.7f)
                )
            }

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp)
                    .padding(top = 8.dp),
                contentAlignment = Alignment.Center
            ) {
                RadarCanvas(
                    devices = devices,
                    isScanning = isScanning,
                    modifier = Modifier.fillMaxWidth(0.92f)
                )
            }

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 12.dp),
                contentAlignment = Alignment.Center
            ) {
                val btnColor = if (isScanning) WarningRed else NeonCyan
                Button(
                    onClick = {
                        if (isScanning) onStopScan()
                        else if (permissionState.allPermissionsGranted) onStartScan()
                        else permissionState.launchMultiplePermissionRequest()
                    },
                    shape = RoundedCornerShape(28.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = btnColor.copy(alpha = 0.15f),
                        contentColor = btnColor
                    ),
                    border = androidx.compose.foundation.BorderStroke(1.5.dp, btnColor),
                    contentPadding = PaddingValues(horizontal = 36.dp, vertical = 14.dp)
                ) {
                    Icon(
                        imageVector = if (isScanning) Icons.Default.Stop else Icons.Default.PlayArrow,
                        contentDescription = null,
                        modifier = Modifier.size(22.dp)
                    )
                    Spacer(Modifier.width(10.dp))
                    Text(
                        if (isScanning) "STOP SCAN" else "START SCAN",
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.sp
                    )
                }
            }

            if (!permissionState.allPermissionsGranted) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 6.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = WarningRed.copy(alpha = 0.12f)
                    ),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(Icons.Default.Warning, null, tint = WarningRed)
                        Spacer(Modifier.width(10.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                "Permissions required",
                                color = SoftWhite,
                                fontWeight = FontWeight.Medium
                            )
                            Text(
                                "Bluetooth + Location needed to detect nearby devices",
                                color = SoftWhite.copy(alpha = 0.7f),
                                fontSize = 12.sp
                            )
                        }
                        TextButton(
                            onClick = { permissionState.launchMultiplePermissionRequest() }
                        ) {
                            Text("Grant", color = NeonCyan)
                        }
                    }
                }
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 6.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    "Detected Signals",
                    style = MaterialTheme.typography.titleLarge,
                    color = SoftWhite
                )
                Text(
                    "${devices.size}",
                    style = MaterialTheme.typography.labelLarge,
                    color = NeonCyan
                )
            }

            LazyColumn(
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
                modifier = Modifier.weight(1f)
            ) {
                items(devices, key = { it.address }) { device ->
                    DeviceCard(device = device)
                }
                if (devices.isEmpty()) {
                    item {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(40.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Icon(
                                imageVector = Icons.Outlined.BluetoothSearching,
                                contentDescription = null,
                                tint = SoftWhite.copy(alpha = 0.3f),
                                modifier = Modifier.size(48.dp)
                            )
                            Spacer(Modifier.height(12.dp))
                            Text(
                                text = if (isScanning)
                                    "Listening for signals (including hidden)..."
                                else
                                    "Press START SCAN to begin",
                                color = SoftWhite.copy(alpha = 0.5f)
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun StatChip(label: String, value: String, color: Color) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            text = value,
            color = color,
            fontWeight = FontWeight.Bold,
            fontSize = 18.sp
        )
        Text(
            text = label,
            color = SoftWhite.copy(alpha = 0.5f),
            fontSize = 11.sp
        )
    }
}

private fun formatUptime(ms: Long): String {
    val sec = ms / 1000
    val min = sec / 60
    val s = sec % 60
    return if (min > 0) "${min}m ${s}s" else "${s}s"
}
