# Clash Studio Android · 1.3

Android Studio 打开本目录，使用 Gradle Wrapper 和内置 JDK。
需要 SDK Platform 37.0、Build Tools 36.0.0、Node.js / pnpm。
先在 `../frontend` 执行 `pnpm install --frozen-lockfile`。

```powershell
../scripts/build-android.ps1 -OpenStudio
# 或在当前目录：
./gradlew.bat assembleDebug testDebugUnitTest lintDebug
```

pnpm 不在 PATH 时传 `-PpnpmExecutable=C:/path/to/pnpm.cmd`。
Gradle 自动执行前端类型检查、生产构建及 assets 同步。
输出 `app/build/outputs/apk/debug/app-debug.apk`，使用本机 debug 签名。
Gradle Wrapper 已升级到 9.8.2，修复 Windows 中文目录下测试工作进程的编码问题。

## 已接入的功能

- 从 HTTPS 订阅链接、UTF-8 Clash YAML 文件或粘贴内容导入，提供不可联网的示例配置。
- 订阅保存、手动刷新、改名和删除；下载上限 8 MB，HTTPS 重定向和超时限制。
- 节点展示与排除、节点及策略组重命名、组成员和规则编辑、草稿检查、保存、历史查看与恢复。
- 节点选择保存在手机，刷新与应用进程重启后仍保留。
- ARM64 Mihomo v1.19.32；Android VpnService 系统授权、前台服务、通知停止、gVisor TCP/UDP 接管。
- 规则 / 全局 / 直连、运行中切换节点与 GLOBAL 出口、真实连接与流量累计、出口 IP 查询。
- 节点 HTTP 延迟测速：VPN 运行时复用内核；停止时按需启动回环测速内核，空闲两分钟回收。
- 代理端口、DNS、IPv6 偏好在下次应用配置时生效；YAML 通过系统文件保存器导出。
- 原有液态玻璃 Dock、安全区、键盘视口、返回键、文件选择和外观设置。

配置保存在应用私有的 `noBackupFilesDir/profiles-v1.json`。更新采用临时文件、落盘及原子替换；版本号避免过期编辑覆盖新数据。解析失败或草稿引用错误时不改变已保存配置；损坏的存储不会自动清空。
YAML 使用 SnakeYAML SafeConstructor，并限制大小、别名展开、层级和集合数量。
最多 50 份订阅、每份最近 5 个历史快照，总数据文件上限 64 MB。

原生接口通过 `WebViewCompat.addWebMessageListener` 仅向
`https://appassets.androidplatform.net` 顶层页面开放，在后台线程执行。
WebView 使用本地 HTTPS 资源源，禁止任意外部子资源和文件 URL；原生下载接口只接受 HTTPS 订阅。文件读写通过系统选择器授权，不申请全盘存储权限。
AndroidX 与 SnakeYAML 的许可随 APK 放在 `assets/licenses/`。

## 内核与 VPN

JNI 库固定 libmihomo-android v0.3.11（bridge ABI 3），Mihomo v1.19.32。
Gradle 首次构建自动下载 AAR，核对固定 SHA-256；仅打包 arm64-v8a。
两份原生库均按 16 KiB ELF 页面边界构建；许可和源码链接随 APK 提供。
源码提交与依赖记录见 [VPN 开发记录](../docs/android-vpn.md)。

首次连接通过 Android 系统 VPN 授权；取消时不建立接口。
VPN 使用前台服务及系统状态栏提示，停止时关闭 TUN fd、代理监听与连接。
运行配置写入应用私有 `noBackupFilesDir/mihomo/`，保持 Fake-IP 映射以避免重启后旧 DNS 缓存指向错误域名。
导入配置不能自行开启控制器、公开监听或桌面 TUN；代理端口绑定 127.0.0.1。
Android 13+ 绕过私有 IPv4 局域网及 IPv6 链路本地路由，便于无线 ADB；较早系统的局域网流量仍经过规则判断。
关闭 IPv6 时不为该地址族添加绕过路由。

应用名为 **Clash Studio Dev**，沿用独立测试包名
`studio.clash.android.validation`，可保留之前开发包的数据升级。
不要求 root，也不使用桌面 TUN 管理员 / Wintun 流程。

## 尚未接入

分应用 VPN、开机 / Always-on VPN、自动刷新、GeoData 手动更新面板、模块分流、AI 预设及订阅发布服务。
Provider 可由内核加载；不支持引用手机外部文件路径的 file Provider。
出口查询目前只返回 IP，暂不提供归属地。
尚无长时间待机、跨 Wi-Fi/蜂窝切换及全部代理协议的完整兼容性验收。

最低 Android 8.0（API 26），目标 API 37。

```powershell
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n studio.clash.android.validation/studio.clash.android.MainActivity
```

构建及验证详情见 [开发记录](../docs/android-features.md)。

## 真机回归

按需构建独立 UID 的测试应用（不会进入主 APK）：

```powershell
./gradlew.bat :vpn-probe:assembleDebug -PincludeVpnProbe=true
adb install -r vpn-probe/build/outputs/apk/debug/vpn-probe-debug.apk
$env:ANDROID_SERIAL = '<adb devices 中的设备标识>'
$env:ADB = '<adb.exe 的完整路径>'
node ../scripts/verify-android-vpn.cjs
```

此脚本要求测试开始前停止现有 VPN，创建自己的临时订阅，结束时停止服务并删除测试订阅。
首次运行若出现系统 VPN 授权框，需用户确认。结果默认写入当前目录的 `artifacts/android-vpn/`。
