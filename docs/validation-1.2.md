# Clash Studio 1.2 构建与验证

产品版本 1.2，程序版本 1.2.0，Android versionCode 7。

交付文件位于 `artifacts/releases/`：Windows 安装版和便携版、Linux x64 tar.gz、Android ARM64 APK、源码 ZIP、`SHA256SUMS-1.2.txt`、`BUILD-REPORT-1.2.json`。

本轮功能包含桌面 TUN 严格模式开关，以及桌面和 Android DNS 防泄漏。用户于 2026-10-27 确认全部验收及功能验证完成；用户自行完成的验收与构建自动化结果分别记录。

此前已执行的可核对检查：PJE110 独立验收包 14 项检查通过，覆盖设置保存、重启保留、真实 VPN、专用 DNS 组、代理故障不回落和关闭恢复；Windows DNS 9 项实际联网检查通过。Windows TUN 等手工验收由用户确认完成。

1.2 版本产物的实际构建、回归、签名、包内容和校验结果以 `BUILD-REPORT-1.2.json` 为准。不把用户验收声明写成自动化或额外设备实测。

Android 使用与 1.1 本地发布包一致的 Android 开发密钥，Release 包关闭调试标志及验收故障读取；Windows EXE 未签名。发行包和对应源码通过 GitHub Release 提供；发布过程不覆盖用户安装。
