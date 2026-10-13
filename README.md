# BlueRadar

**Advanced Bluetooth Proximity Radar** — Detects even the weakest and hidden Bluetooth signals and alerts you.

**Builds are green.** Download APK + EXE from Actions artifacts.

## Feature list (Android + Windows)

### Scanning & detection
1. BLE continuous scan
2. Classic Bluetooth discovery (Android)
3. Ultra-sensitive down to **-120 dBm**
4. No filters — finds empty-name / hidden devices
5. 90s memory for intermittent advertisers (AirTags, trackers)
6. Aggressive match mode
7. RSSI → distance estimation
8. Manufacturer parsing (Apple, Google, Tile, Samsung…)
9. Device type classification (Phone, Headset, Tracker…)
10. Signal history per device
11. First seen / last seen / times seen
12. Periodic classic rediscovery (Android)

### Alerts & warnings
13. Adjustable warning distance (default 10 m)
14. Multi-level proximity (Immediate / Near / Medium / Far)
15. Sound alerts (Windows)
16. Vibration patterns (Android)
17. High-priority notifications (Android)
18. Title-bar flash alert (Windows)
19. Alert cooldown (anti-spam)
20. Foreground service (Android — scan with screen off)

### Device management
21. Search by name or MAC
22. Filter: hidden only
23. Filter: in-range only
24. Sort by distance / RSSI / name / last seen
25. Favorites
26. Blacklist / ignore
27. Copy MAC to clipboard
28. Clear device list
29. Session unique device counter
30. Persist favorites & blacklist

### Export & settings
31. Export CSV
32. Export JSON
33. Settings: warning distance slider
34. Settings: min RSSI sensitivity
35. Settings: sound on/off
36. Settings: flash title on/off
37. Live stats: visible / in range / hidden / alerts / uptime

### UI
38. Dark neon cyber theme
39. Animated radar sweep (Android)
40. Color-coded distance badges
41. Signal strength bars (Android)
42. HIDDEN badges
43. IN RANGE badges
44. Responsive device cards
45. Material 3 Compose UI (Android)
46. CustomTkinter polished UI (Windows)

## Download builds

1. Open [Actions](https://github.com/someone405-ship-it/BlueRadar/actions)
2. Latest **green** run → download **BlueRadar-apk** and **BlueRadar-exe**

Or **Run workflow** manually.

## Local build

**Android**
```bash
git clone https://github.com/someone405-ship-it/BlueRadar.git
cd BlueRadar
gradle wrapper --gradle-version 8.7
./gradlew assembleDebug
```

**Windows**
```bash
cd windows
pip install -r requirements.txt
pyinstaller --onefile --windowed --name BlueRadar blueradar_windows.py
```

## License
MIT
