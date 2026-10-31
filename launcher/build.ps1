$ErrorActionPreference = 'Stop'
$alphaRoot = Split-Path $PSScriptRoot -Parent
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $compiler /nologo /target:winexe ("/out:" + (Join-Path $alphaRoot 'ClashStudioLauncher.exe')) ("/win32icon:" + (Join-Path $alphaRoot 'src-tauri/icons/icon.ico')) /reference:System.Windows.Forms.dll (Join-Path $PSScriptRoot 'Launcher.cs')
if ($LASTEXITCODE -ne 0) { throw 'Launcher build failed.' }
