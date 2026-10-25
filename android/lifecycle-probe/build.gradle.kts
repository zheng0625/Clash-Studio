plugins { id("com.android.application") }
android {
    namespace = "studio.clash.lifecycleprobe"
    compileSdk = 37
    defaultConfig { applicationId = "studio.clash.lifecycleprobe"; minSdk = 29; targetSdk = 37; versionCode = 1; versionName = "1" }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
}
