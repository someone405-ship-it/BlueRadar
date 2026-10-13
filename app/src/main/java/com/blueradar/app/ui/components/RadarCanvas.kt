package com.blueradar.app.ui.components

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.center
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import com.blueradar.app.model.BluetoothDeviceInfo
import com.blueradar.app.model.ProximityLevel
import com.blueradar.app.ui.theme.*
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin

@Composable
fun RadarCanvas(
    devices: List<BluetoothDeviceInfo>,
    isScanning: Boolean,
    modifier: Modifier = Modifier
) {
    val infiniteTransition = rememberInfiniteTransition(label = "radar")
    val sweepAngle by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 2800, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "sweep"
    )
    val pulse by infiniteTransition.animateFloat(
        initialValue = 0.85f,
        targetValue = 1.15f,
        animationSpec = infiniteRepeatable(
            animation = tween(1400, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulse"
    )

    Canvas(modifier = modifier.fillMaxWidth().aspectRatio(1f)) {
        val center = size.center
        val maxRadius = min(size.width, size.height) / 2f * 0.92f

        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(NeonCyan.copy(alpha = 0.08f), Color.Transparent),
                center = center, radius = maxRadius * 1.1f
            ),
            radius = maxRadius * 1.1f, center = center
        )

        listOf(0.25f, 0.5f, 0.75f, 1.0f).forEachIndexed { index, fraction ->
            val radius = maxRadius * fraction
            val color = when (index) {
                0 -> WarningRed.copy(alpha = 0.35f)
                1 -> NeonOrange.copy(alpha = 0.25f)
                2 -> NeonCyan.copy(alpha = 0.20f)
                else -> NeonCyan.copy(alpha = 0.12f)
            }
            drawCircle(color = color, radius = radius, center = center, style = Stroke(width = 1.5f))
        }

        drawLine(color = GridLine, start = Offset(center.x - maxRadius, center.y), end = Offset(center.x + maxRadius, center.y), strokeWidth = 1f)
        drawLine(color = GridLine, start = Offset(center.x, center.y - maxRadius), end = Offset(center.x, center.y + maxRadius), strokeWidth = 1f)

        if (isScanning) {
            rotate(sweepAngle, pivot = center) {
                val sweepBrush = Brush.sweepGradient(
                    0.0f to Color.Transparent, 0.85f to Color.Transparent,
                    0.95f to NeonCyan.copy(alpha = 0.15f), 1.0f to NeonCyan.copy(alpha = 0.55f),
                    center = center
                )
                drawCircle(brush = sweepBrush, radius = maxRadius, center = center)
                drawLine(color = NeonCyan.copy(alpha = 0.9f), start = center, end = Offset(center.x, center.y - maxRadius), strokeWidth = 2.5f, cap = StrokeCap.Round)
            }
        }

        drawCircle(color = NeonCyan.copy(alpha = 0.6f * pulse), radius = 8f * pulse, center = center)
        drawCircle(color = NeonCyan, radius = 4f, center = center)

        devices.forEach { device ->
            val angleSeed = device.address.hashCode().toFloat()
            val angle = Math.toRadians((angleSeed % 360).toDouble())
            val distanceFraction = (device.estimatedDistanceMeters / 12.0).coerceIn(0.05, 0.98)
            val r = maxRadius * distanceFraction.toFloat()
            val x = center.x + (r * cos(angle)).toFloat()
            val y = center.y + (r * sin(angle)).toFloat()

            val blipColor = when (device.proximityLevel) {
                ProximityLevel.IMMEDIATE -> WarningRed
                ProximityLevel.NEAR -> NeonOrange
                ProximityLevel.MEDIUM -> NeonCyan
                ProximityLevel.FAR -> NeonGreen.copy(alpha = 0.7f)
            }
            drawCircle(color = blipColor.copy(alpha = 0.25f), radius = 14f, center = Offset(x, y))
            drawCircle(color = blipColor, radius = 6f, center = Offset(x, y))
            drawCircle(color = Color.White.copy(alpha = 0.8f), radius = 2f, center = Offset(x - 1.5f, y - 1.5f))
        }
    }
}
