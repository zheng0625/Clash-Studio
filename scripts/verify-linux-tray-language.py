"""Inspect the real GNOME D-Bus menu using an isolated desktop data directory.

This checks native rendering of persisted preferences, not a simulated UI click.
"""
import json
from pathlib import Path
import subprocess
import sys
import time

data=Path(sys.argv[1]).resolve()
assert data.name=='language-test', 'Only run against the isolated language test profile'
path=data/'desktop-language.json'
previous=path.read_bytes() if path.exists() else None
menu='/org/ayatana/NotificationItem/tray_icon_tray_app_main_tray/Menu'
names=[line.split()[0] for line in subprocess.check_output(['busctl','--user','--no-pager','--no-legend','list'],text=True).splitlines() if 'ClashStudio' in line and line.startswith(':')]
def layout():
    for name in names:
        subprocess.run(['gdbus','call','--session','--dest',name,'--object-path',menu,'--method','com.canonical.dbusmenu.AboutToShow','0'],text=True,capture_output=True,timeout=3)
        result=subprocess.run(['gdbus','call','--session','--dest',name,'--object-path',menu,'--method','com.canonical.dbusmenu.GetLayout','--','0','-1','[]'],text=True,capture_output=True,timeout=3)
        if not result.returncode:return result.stdout
    raise AssertionError('Native tray menu not exported')
try:
    for language,labels in [('en',['Open Clash Studio','Enable proxy','Proxy mode','Traffic capture','Quit']),('zh-CN',['打开 Clash Studio','开启代理','代理模式','接管方式','退出']),('en',['Open Clash Studio','Enable proxy','Proxy mode','Traffic capture','Quit'])]:
        path.write_text(json.dumps(language),encoding='utf-8')
        for _ in range(40):
            value=layout()
            if all(label in value for label in labels):break
            time.sleep(.2)
        else:raise AssertionError('Native tray language did not change: '+language)
    print(json.dumps({'native_dbus_menu':True,'english_chinese_english':True,'restart_not_required':True}))
finally:
    if previous is None:path.unlink(missing_ok=True)
    else:path.write_bytes(previous)
