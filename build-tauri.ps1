param([switch]$SkipFrontend)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'dev-env.ps1')
Push-Location $PSScriptRoot
try {
    if (-not $SkipFrontend) {
        & pnpm --dir frontend build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    }
    & cargo build --manifest-path src-tauri\Cargo.toml --release
    if ($LASTEXITCODE -ne 0) { throw 'Tauri Rust build failed.' }
    Copy-Item -LiteralPath 'src-tauri\target\release\clash-studio.exe' -Destination 'ClashStudio.exe' -Force
    Write-Output 'Built ClashStudio.exe'
} finally { Pop-Location }
