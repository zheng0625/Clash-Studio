param([switch]$SkipFrontend, [switch]$UiTest)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'dev-env.ps1')
Push-Location $PSScriptRoot
$previousTauriConfig = $env:TAURI_CONFIG
try {
    if ($UiTest) { $env:TAURI_CONFIG = Get-Content -LiteralPath 'src-tauri/tauri.ui-test.conf.json' -Raw }
    if (-not $SkipFrontend) {
        & pnpm --dir frontend build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    }
    & cargo build --manifest-path src-tauri\Cargo.toml --release
    if ($LASTEXITCODE -ne 0) { throw 'Tauri Rust build failed.' }
    Copy-Item -LiteralPath 'src-tauri\target\release\clash-studio.exe' -Destination 'ClashStudio.exe' -Force
    Write-Output 'Built ClashStudio.exe'
} finally { $env:TAURI_CONFIG = $previousTauriConfig; Pop-Location }
