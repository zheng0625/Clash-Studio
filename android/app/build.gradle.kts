import org.gradle.api.file.DirectoryProperty
import org.gradle.api.file.RegularFileProperty
import org.gradle.api.file.FileSystemOperations
import javax.inject.Inject
import java.io.File
import java.net.URI
import java.security.MessageDigest

plugins { id("com.android.application") }

abstract class PrepareUiAssets : DefaultTask() {
    @get:InputDirectory abstract val inputDirectory: DirectoryProperty
    @get:InputFile abstract val changelog: RegularFileProperty
    @get:OutputDirectory abstract val outputDirectory: DirectoryProperty
    @get:Inject abstract val fileSystem: FileSystemOperations
    @TaskAction fun syncAssets() {
        fileSystem.sync {
            from(inputDirectory)
            from(changelog)
            into(outputDirectory)
            exclude("ui-editor.html", "ui-preview.html", "ui-android.html")
        }
    }
}

android {
    namespace = "studio.clash.android"
    compileSdk = 37
    defaultConfig {
        applicationId = "studio.clash.android.validation"
        minSdk = 26
        targetSdk = 37
        versionCode = 8
        versionName = "1.3.0"
        manifestPlaceholders["appLabel"] = "Clash Studio"
        ndk { abiFilters += "arm64-v8a" }
    }
    signingConfigs {
        create("production") {
            val keyPath = providers.environmentVariable("CLASHSTUDIO_KEYSTORE").orNull
            if (keyPath != null) {
                storeFile = file(keyPath)
                storePassword = providers.environmentVariable("CLASHSTUDIO_STORE_PASSWORD").get()
                keyAlias = "clashstudio"
                keyPassword = providers.environmentVariable("CLASHSTUDIO_STORE_PASSWORD").get()
            }
        }
    }
    buildTypes {
        getByName("debug") {
            if (providers.gradleProperty("acceptanceBuild").orNull == "true") {
                applicationIdSuffix = ".acceptance"
                manifestPlaceholders["appLabel"] = "Clash Studio · 验收"
            }
        }
        getByName("release") {
            isDebuggable = false
            if (providers.environmentVariable("CLASHSTUDIO_KEYSTORE").isPresent) {
                signingConfig = signingConfigs.getByName("production")
            }
        }
    }
    sourceSets.getByName("test").resources.srcDir("../../tests/fixtures")
    buildFeatures { buildConfig = true }
    packaging { jniLibs { useLegacyPackaging = true } }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

// Package the same production Vue bundle used by desktop. Never ship test fixtures.
val frontendDir = rootProject.layout.projectDirectory.dir("../frontend")
val buildFrontend = tasks.register<Exec>("buildFrontend") {
    workingDir(frontendDir)
    val pnpm = providers.gradleProperty("pnpmExecutable").orElse("pnpm").get()
    if (System.getProperty("os.name").startsWith("Windows")) commandLine("cmd", "/c", pnpm, "run", "build")
    else commandLine(pnpm, "run", "build")
    inputs.dir(frontendDir.dir("src"))
    inputs.dir(frontendDir.dir("public"))
    inputs.files(frontendDir.file("package.json"), frontendDir.file("pnpm-lock.yaml"), frontendDir.file("index.html"), frontendDir.file("vite.config.ts"), frontendDir.file("tsconfig.json"))
    outputs.dir(frontendDir.dir("dist"))
}
val syncFrontend = tasks.register<PrepareUiAssets>("syncFrontend") {
    dependsOn(buildFrontend)
    inputDirectory.set(frontendDir.dir("dist"))
    changelog.set(rootProject.layout.projectDirectory.file("../CHANGELOG.md"))
    outputDirectory.set(layout.buildDirectory.dir("generated/ui-assets"))
}
androidComponents.onVariants { variant ->
    variant.sources.assets?.addGeneratedSourceDirectory(syncFrontend, PrepareUiAssets::outputDirectory)
}

val mihomoAar = layout.projectDirectory.file("libs/libmihomo-android-v0.3.11.aar")
val prepareMihomo = tasks.register("prepareMihomo") {
    outputs.file(mihomoAar)
    doLast {
        val target = mihomoAar.asFile
        if (!target.exists()) {
            target.parentFile.mkdirs()
            val temporary = File(target.parentFile, target.name + ".tmp")
            URI("https://github.com/oviron/libmihomo-android/releases/download/v0.3.11/" + target.name).toURL().openConnection().apply {
                connectTimeout = 30000; readTimeout = 120000
            }.getInputStream().use { input -> temporary.outputStream().use { input.copyTo(it) } }
            temporary.renameTo(target)
        }
        val hash = MessageDigest.getInstance("SHA-256").digest(target.readBytes()).joinToString("") { "%02x".format(it) }
        check(hash == "01bc41748840c8200bbaf08c044ba8704e35303a3179b75a3cce8517c8944251") { "Mihomo AAR checksum mismatch; remove app/libs/${target.name} and retry" }
    }
}
dependencies {
    implementation(files(mihomoAar).builtBy(prepareMihomo))
    implementation("org.jetbrains.kotlin:kotlin-stdlib:2.2.21")
    implementation("androidx.webkit:webkit:1.14.0")
    implementation("androidx.activity:activity:1.10.1")
    implementation("org.yaml:snakeyaml:2.7")
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")
    implementation("com.google.zxing:core:3.5.3")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20260814")
}
