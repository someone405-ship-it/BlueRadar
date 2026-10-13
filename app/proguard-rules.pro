# Keep Bluetooth related classes
-keep class android.bluetooth.** { *; }
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
