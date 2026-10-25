param(
    [string]$StudioHome,
    [string]$SdkPath = "$env:LOCALAPPDATA/Android/Sdk",
    [string]$PnpmExecutable = 'pnpm',
    [switch]$OpenStudio,
    [switch]$Release
)
$ErrorActionPreference = 'Stop'
$project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../android'))
if (-not $StudioHome) {
    $shortcutPath = "$env:ProgramData/Microsoft/Windows/Start Menu/Programs/Android Studio/Android Studio.lnk"
    if (Test-Path -LiteralPath $shortcutPath) {
        $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcutPath)
        $StudioHome = Split-Path (Split-Path $shortcut.TargetPath -Parent) -Parent
    } else { $StudioHome = "$env:ProgramFiles/Android/Android Studio" }
}
$studioJava = Join-Path $StudioHome 'jbr'
if (-not (Test-Path -LiteralPath "$studioJava/bin/java.exe")) { throw 'Android Studio bundled JDK not found. Specify -StudioHome.' }
if (-not (Test-Path -LiteralPath "$SdkPath/platforms/android-37.0/android.jar")) { throw 'Install Android SDK Platform 37.0 through SDK Manager first.' }
if (-not (Get-Command $PnpmExecutable -ErrorAction SilentlyContinue)) { throw 'pnpm not found. Install it or specify -PnpmExecutable.' }
$sdkValue = $SdkPath.Replace('\','/').Replace(':','\:')
Set-Content -LiteralPath (Join-Path $project 'local.properties') -Value "sdk.dir=$sdkValue" -Encoding ascii
$previousJava = $env:JAVA_HOME
try {
    $env:JAVA_HOME = $studioJava
    Push-Location $project
    try {
        if ($Release) {
            if (-not $env:CLASHSTUDIO_KEYSTORE -or -not $env:CLASHSTUDIO_STORE_PASSWORD) { throw 'Set CLASHSTUDIO_KEYSTORE and CLASHSTUDIO_STORE_PASSWORD for a signed release.' }
            & './gradlew.bat' --no-daemon :app:assembleRelease :app:testDebugUnitTest :app:lintRelease "-PpnpmExecutable=$PnpmExecutable"
        } else {
            & './gradlew.bat' --no-daemon assembleDebug testDebugUnitTest lintDebug "-PpnpmExecutable=$PnpmExecutable"
        }
        if ($LASTEXITCODE -ne 0) { throw "Android build failed: $LASTEXITCODE" }
    } finally { Pop-Location }
} finally { $env:JAVA_HOME = $previousJava }
if ($Release) { Write-Host (Join-Path $project 'app/build/outputs/apk/release/app-release.apk') }
else { Write-Host (Join-Path $project 'app/build/outputs/apk/debug/app-debug.apk') }
if ($OpenStudio) { Start-Process -FilePath (Join-Path $StudioHome 'bin/studio64.exe') -ArgumentList "`"$project`"" }
