"""Build a per-user NSIS installer from the clean portable release.

Run using Python on Linux/WSL with makensis installed. No global Python needed
on the target Windows machine. Uninstall retains application data.
"""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.0'
RELEASES = ROOT / 'artifacts/releases'
PAYLOAD = RELEASES / f'ClashStudio-{VERSION}-portable-windows-x64'
OUTPUT = RELEASES / f'ClashStudio-{VERSION}-setup-windows-x64.exe'
BUILD = ROOT / 'artifacts' / f'installer-{VERSION}'
BUILD.mkdir(parents=True, exist_ok=True)
if OUTPUT.exists():
    raise SystemExit('Keep existing release; select a new version.')
files = [p for p in sorted(PAYLOAD.rglob('*')) if p.is_file() and p.relative_to(PAYLOAD).parts[0] not in
         {'data', 'portable.json', 'manifest.json', '管理员启动.cmd', '使用说明.txt'}]
assert (PAYLOAD / 'ClashStudio.exe').is_file() and len(files) > 100
(BUILD / 'installed.json').write_text(json.dumps({'version': VERSION, 'data': '%LOCALAPPDATA%/ClashStudio'}), encoding='utf-8')


def literal(value):
    return str(value).replace('$', '$$').replace('"', '$\\"')


lines = [f'''Unicode true
!include "MUI2.nsh"
Name "Clash Studio {VERSION}"
OutFile "{literal(OUTPUT)}"
InstallDir "$LOCALAPPDATA\\Programs\\Clash Studio"
InstallDirRegKey HKCU "Software\\ClashStudio" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
Icon "{literal(ROOT / 'src-tauri/icons/icon.ico')}"
UninstallIcon "{literal(ROOT / 'src-tauri/icons/icon.ico')}"
VIProductVersion "{VERSION}.0.0"
VIAddVersionKey /LANG=1033 "ProductName" "Clash Studio"
VIAddVersionKey /LANG=1033 "FileDescription" "Clash Studio Setup"
VIAddVersionKey /LANG=1033 "FileVersion" "{VERSION}"
VIAddVersionKey /LANG=1033 "LegalCopyright" "Clash Studio contributors"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "{literal(ROOT / 'LICENSE')}"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"
Section "Clash Studio"
SetShellVarContext current
IfFileExists "$INSTDIR\\*" 0 fresh
IfFileExists "$INSTDIR\\installed.json" check_running 0
MessageBox MB_OK|MB_ICONSTOP "Please select an empty folder or an existing Clash Studio installation." /SD IDOK
SetErrorLevel 2
Abort
check_running:
IfFileExists "$INSTDIR\\ClashStudio.exe" 0 fresh
ClearErrors
FileOpen $0 "$INSTDIR\\ClashStudio.exe" a
IfErrors locked 0
FileClose $0
Goto fresh
locked:
MessageBox MB_OK|MB_ICONSTOP "Please exit Clash Studio before updating." /SD IDOK
SetErrorLevel 2
Abort
fresh:
''']
directories = set()
last = None
for path in files:
    relative = path.relative_to(PAYLOAD)
    parent = str(relative.parent).replace('/', '\\')
    if parent != last:
        lines.append(f'SetOutPath "$INSTDIR\\{literal(parent)}"')
        last = parent
    lines.append(f'File "{literal(path)}"')
    directories.update(relative.parents)
lines += [f'''SetOutPath "$INSTDIR"
File "{literal(BUILD / 'installed.json')}"
WriteUninstaller "$INSTDIR\\Uninstall.exe"
CreateDirectory "$SMPROGRAMS\\Clash Studio"
CreateShortcut "$SMPROGRAMS\\Clash Studio\\Clash Studio.lnk" "$INSTDIR\\ClashStudio.exe" "" "$INSTDIR\\ClashStudio.exe"
CreateShortcut "$SMPROGRAMS\\Clash Studio\\Uninstall.lnk" "$INSTDIR\\Uninstall.exe"
WriteRegStr HKCU "Software\\ClashStudio" "InstallDir" "$INSTDIR"
WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\ClashStudio" "DisplayName" "Clash Studio"
WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\ClashStudio" "DisplayVersion" "{VERSION}"
WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\ClashStudio" "DisplayIcon" "$INSTDIR\\ClashStudio.exe"
WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\ClashStudio" "InstallLocation" "$INSTDIR"
WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\ClashStudio" "UninstallString" '$\\"$INSTDIR\\Uninstall.exe$\\"'
WriteRegDWORD HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\ClashStudio" "NoModify" 1
WriteRegDWORD HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\ClashStudio" "NoRepair" 1
SectionEnd
Section "Uninstall"
SetShellVarContext current
ClearErrors
FileOpen $0 "$INSTDIR\\ClashStudio.exe" a
IfErrors un_locked 0
FileClose $0
Goto un_delete
un_locked:
MessageBox MB_OK|MB_ICONSTOP "Please exit Clash Studio before uninstalling." /SD IDOK
SetErrorLevel 2
Abort
un_delete:
''']
for path in files:
    lines.append('Delete "$INSTDIR\\' + literal(str(path.relative_to(PAYLOAD)).replace('/', '\\')) + '"')
for path in sorted(directories, key=lambda p: len(p.parts), reverse=True):
    if str(path) != '.':
        lines.append('RMDir "$INSTDIR\\' + literal(str(path).replace('/', '\\')) + '"')
lines += ['''Delete "$INSTDIR\\installed.json"
Delete "$INSTDIR\\Uninstall.exe"
RMDir "$INSTDIR"
ReadRegStr $0 HKCU "Software\\ClashStudio" "InstallDir"
StrCmp $0 "$INSTDIR" 0 un_done
DeleteRegKey HKCU "Software\\ClashStudio"
DeleteRegKey HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\ClashStudio"
Delete "$SMPROGRAMS\\Clash Studio\\Clash Studio.lnk"
Delete "$SMPROGRAMS\\Clash Studio\\Uninstall.lnk"
RMDir "$SMPROGRAMS\\Clash Studio"
un_done:
SectionEnd
''']
script = BUILD / 'setup.nsi'
script.write_text('\n'.join(lines), encoding='utf-8-sig')
subprocess.run(['makensis', '-V2', str(script)], check=True)
digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
OUTPUT.with_suffix('.exe.sha256').write_text(digest + '  ' + OUTPUT.name + '\n', encoding='ascii')
print(json.dumps({'installer': str(OUTPUT), 'bytes': OUTPUT.stat().st_size, 'sha256': digest}))
