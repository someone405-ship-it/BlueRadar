# BlueRadar

**Advanced Bluetooth Proximity Radar** — Detects even the weakest and hidden Bluetooth signals within ~10 meters and alerts you instantly.

## Features

### Ultra-sensitive / Hidden device detection
- Accepts signals as weak as **-120 dBm**
- No advertisement filters — catches devices with empty names ("HIDDEN")
- 90-second memory for intermittent advertisers (AirTags, trackers, etc.)
- Aggressive BLE scan mode + Classic Bluetooth rediscovery every 12s
- Manufacturer detection (Apple, Google, Tile, Samsung, Xiaomi…)
- Automatic device type classification

### Alerts
- Multi-level proximity warnings (Immediate / Near / Medium)
- Vibration patterns + high-priority notifications
- Foreground service keeps scanning with screen off

### Fancy cyber-radar UI
- Animated neon radar sweep
- Live device blips colored by distance
- Signal strength bars, distance badges, HIDDEN tag
- Material 3 dark theme

### Cross-platform
- Android (Kotlin + Jetpack Compose)
- Windows companion (Python + Bleak → .exe)

## Get the APK and EXE

1. Go to **Actions** tab
2. Select **Build BlueRadar APK + EXE**
3. Click **Run workflow**
4. Download artifacts when finished:
   - `BlueRadar-apk`
   - `BlueRadar-exe`

## Local build (Android)

```bash
git clone https://github.com/someone405-ship-it/BlueRadar.git
cd BlueRadar
gradle wrapper --gradle-version 8.7   # once
./gradlew assembleDebug
# APK → app/build/outputs/apk/debug/app-debug.apk
```

## Local Windows EXE

```bash
cd windows
pip install -r requirements.txt
pyinstaller --onefile --windowed --name BlueRadar blueradar_windows.py
# → dist/BlueRadar.exe
```

## Permissions (Android)
- Nearby devices / Bluetooth Scan + Connect
- Location (required by Android for BLE scanning)
- Notifications

## License
MIT
