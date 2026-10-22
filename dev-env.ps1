$ErrorActionPreference = 'Stop'
$alphaRoot = $PSScriptRoot
$env:RUSTUP_HOME = Join-Path $alphaRoot '.toolchain\rustup'
$env:CARGO_HOME = Join-Path $alphaRoot '.toolchain\cargo'
$env:Path = (Join-Path $env:CARGO_HOME 'bin') + ';' + $env:Path
$vswherePath = 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path -LiteralPath $vswherePath)) { throw 'Install Microsoft C++ Build Tools first.' }
$vsInstall = & $vswherePath -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vsInstall) { throw 'MSVC x64 build tools were not found.' }
$vcvars = Join-Path $vsInstall 'VC\Auxiliary\Build\vcvars64.bat'
$environmentLines = & $env:ComSpec /d /c "call `"$vcvars`" >nul && set"
foreach ($line in $environmentLines) {
    $separator = $line.IndexOf('=')
    if ($separator -gt 0) { [Environment]::SetEnvironmentVariable($line.Substring(0,$separator),$line.Substring($separator+1),'Process') }
}
Write-Output 'Local Rust MSVC environment ready.'
