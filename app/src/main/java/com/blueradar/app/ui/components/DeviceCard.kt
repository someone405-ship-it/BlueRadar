package com.blueradar.app.ui.components

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.BluetoothSearching
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.blueradar.app.model.BluetoothDeviceInfo
import com.blueradar.app.model.DeviceType
import com.blueradar.app.model.ProximityLevel
import com.blueradar.app.ui.theme.*

@Composable
fun DeviceCard(device: BluetoothDeviceInfo, modifier: Modifier = Modifier) {
    val borderColor by animateColorAsState(
        targetValue = when (device.proximityLevel) {
            ProximityLevel.IMMEDIATE -> WarningRed
            ProximityLevel.NEAR -> NeonOrange
            ProximityLevel.MEDIUM -> NeonCyan
            ProximityLevel.FAR -> Color.Transparent
        },
        animationSpec = tween(400), label = "border"
    )
    val bgBrush = Brush.horizontalGradient(
        colors = listOf(
            DarkPanel,
            when (device.proximityLevel) {
                ProximityLevel.IMMEDIATE -> WarningRed.copy(alpha = 0.12f)
                ProximityLevel.NEAR -> NeonOrange.copy(alpha = 0.08f)
                else -> DarkPanel
            }
        )
    )
    Card(
        modifier = modifier.fillMaxWidth().border(1.dp, borderColor, RoundedCornerShape(16.dp)),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color.Transparent)
    ) {
        Box(modifier = Modifier.background(bgBrush).padding(14.dp)) {
            Column {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(imageVector = iconForType(device.deviceType), contentDescription = null, tint = NeonCyan, modifier = Modifier.size(22.dp))
                        Spacer(Modifier.width(10.dp))
                        Column {
                            Text(text = device.displayName, style = MaterialTheme.typography.titleLarge, color = SoftWhite, maxLines = 1)
                            Text(text = device.address, style = MaterialTheme.typography.labelSmall, color = SoftWhite.copy(alpha = 0.5f), fontFamily = FontFamily.Monospace)
                        }
                    }
                    Surface(
                        shape = RoundedCornerShape(20.dp),
                        color = when (device.proximityLevel) {
                            ProximityLevel.IMMEDIATE -> WarningRed.copy(alpha = 0.25f)
                            ProximityLevel.NEAR -> NeonOrange.copy(alpha = 0.2f)
                            else -> NeonCyan.copy(alpha = 0.15f)
                        }
                    ) {
                        Text(
                            text = "%.1f m".format(device.estimatedDistanceMeters),
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                            color = when (device.proximityLevel) {
                                ProximityLevel.IMMEDIATE -> WarningRed
                                ProximityLevel.NEAR -> NeonOrange
                                else -> NeonCyan
                            },
                            fontWeight = FontWeight.Bold, fontSize = 13.sp
                        )
                    }
                }
                Spacer(Modifier.height(10.dp))
                SignalBar(percent = device.signalStrengthPercent, rssi = device.rssi)
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
                    InfoChip(label = if (device.isBle) "BLE" else "Classic", color = NeonGreen)
                    device.manufacturer?.let { InfoChip(label = it, color = NeonMagenta) }
                    InfoChip(label = device.deviceType.name.lowercase().replaceFirstChar { it.uppercase() }, color = SoftWhite.copy(alpha = 0.7f))
                    if (device.name.isNullOrBlank()) InfoChip(label = "HIDDEN", color = WarningRed)
                    if (device.isInWarningRange) InfoChip(label = "IN RANGE", color = WarningRed)
                }
            }
        }
    }
}

@Composable
private fun SignalBar(percent: Int, rssi: Int) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(text = "$rssi dBm", style = MaterialTheme.typography.labelSmall, color = SoftWhite.copy(alpha = 0.6f), modifier = Modifier.width(58.dp))
        Box(modifier = Modifier.weight(1f).height(6.dp).clip(RoundedCornerShape(3.dp)).background(GridLine)) {
            Box(modifier = Modifier.fillMaxHeight().fillMaxWidth(percent / 100f).background(Brush.horizontalGradient(listOf(NeonCyan, NeonGreen))))
        }
        Spacer(Modifier.width(8.dp))
        Text(text = "$percent%", style = MaterialTheme.typography.labelSmall, color = NeonCyan, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun InfoChip(label: String, color: Color) {
    Surface(shape = RoundedCornerShape(6.dp), color = color.copy(alpha = 0.12f)) {
        Text(text = label, modifier = Modifier.padding(horizontal = 7.dp, vertical = 2.dp), style = MaterialTheme.typography.labelSmall, color = color, fontSize = 10.sp)
    }
}

private fun iconForType(type: DeviceType) = when (type) {
    DeviceType.PHONE -> Icons.Default.Smartphone
    DeviceType.HEADSET -> Icons.Default.Headphones
    DeviceType.SPEAKER -> Icons.Default.VolumeUp
    DeviceType.TRACKER -> Icons.Default.LocationOn
    DeviceType.WEARABLE -> Icons.Default.Watch
    DeviceType.COMPUTER -> Icons.Default.Computer
    DeviceType.KEYBOARD_MOUSE -> Icons.Default.Keyboard
    DeviceType.UNKNOWN -> Icons.Outlined.BluetoothSearching
}
