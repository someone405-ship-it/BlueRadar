package com.blueradar.app.util

import com.blueradar.app.model.DeviceType

object ManufacturerParser {

    private val knownManufacturers = mapOf(
        0x004C to "Apple",
        0x0006 to "Microsoft",
        0x00E0 to "Google",
        0x0075 to "Samsung",
        0x0499 to "Ruuvi",
        0x0157 to "Tile",
        0x00D2 to "Sony",
        0x0087 to "Garmin",
        0x0131 to "Cypress",
        0x0059 to "Nordic Semiconductor",
        0x000F to "Broadcom",
        0x02E5 to "Espressif",
        0x00A0 to "Xiaomi",
        0x038F to "Xiaomi",
        0x015E to "Huawei"
    )

    fun parseManufacturer(scanRecord: ByteArray?): Pair<String?, DeviceType> {
        if (scanRecord == null || scanRecord.size < 4) return null to DeviceType.UNKNOWN

        var i = 0
        while (i < scanRecord.size - 1) {
            val length = scanRecord[i].toInt() and 0xFF
            if (length == 0 || i + length >= scanRecord.size) break
            val type = scanRecord[i + 1].toInt() and 0xFF

            if (type == 0xFF && length >= 3) {
                val companyId = ((scanRecord[i + 3].toInt() and 0xFF) shl 8) or
                        (scanRecord[i + 2].toInt() and 0xFF)
                val name = knownManufacturers[companyId]
                val deviceType = guessTypeFromManufacturer(companyId, scanRecord, i + 4, length - 3)
                return name to deviceType
            }
            i += length + 1
        }
        return null to DeviceType.UNKNOWN
    }

    private fun guessTypeFromManufacturer(
        companyId: Int,
        data: ByteArray,
        offset: Int,
        length: Int
    ): DeviceType {
        return when (companyId) {
            0x004C -> {
                if (length >= 1) {
                    val subtype = data.getOrNull(offset)?.toInt()?.and(0xFF) ?: 0
                    when {
                        subtype == 0x12 || subtype == 0x10 -> DeviceType.TRACKER
                        else -> DeviceType.PHONE
                    }
                } else DeviceType.PHONE
            }
            0x0157, 0x00E0 -> DeviceType.TRACKER
            0x0075 -> DeviceType.PHONE
            0x0006 -> DeviceType.COMPUTER
            else -> DeviceType.UNKNOWN
        }
    }

    fun classifyByName(name: String?): DeviceType {
        if (name.isNullOrBlank()) return DeviceType.UNKNOWN
        val lower = name.lowercase()
        return when {
            lower.contains("airpods") || lower.contains("buds") ||
                    lower.contains("headset") || lower.contains("headphone") ||
                    lower.contains("beats") -> DeviceType.HEADSET
            lower.contains("airtag") || lower.contains("tile") ||
                    lower.contains("smarttag") || lower.contains("tracker") ||
                    lower.contains("find my") -> DeviceType.TRACKER
            lower.contains("watch") || lower.contains("band") ||
                    lower.contains("fitbit") || lower.contains("galaxy watch") -> DeviceType.WEARABLE
            lower.contains("speaker") || lower.contains("soundbar") ||
                    lower.contains("homepod") || lower.contains("echo") -> DeviceType.SPEAKER
            lower.contains("iphone") || lower.contains("pixel") ||
                    lower.contains("galaxy") || lower.contains("phone") -> DeviceType.PHONE
            lower.contains("macbook") || lower.contains("laptop") ||
                    lower.contains("pc") || lower.contains("desktop") -> DeviceType.COMPUTER
            lower.contains("keyboard") || lower.contains("mouse") ||
                    lower.contains("trackpad") -> DeviceType.KEYBOARD_MOUSE
            else -> DeviceType.UNKNOWN
        }
    }
}
