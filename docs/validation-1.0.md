# Clash Studio 1.0 构建与验证

2026-10-25。应用构建版本 1.0.0。

- Windows x64：便携 ZIP、NSIS 安装 EXE；Rust 6 项测试通过，包内 Python/真实 Mihomo 代理 HTTP 200、节点选择和重启恢复通过。
- Linux x64：Ubuntu 22.04 基线 tar.gz；Rust 7 项测试通过，包内代理 HTTP 200、三种模式和托盘启停检查通过。
- Android arm64-v8a：Release APK，独立正式签名，非 debuggable；36 项单元测试、debug/release lint、APK 签名校验通过。旧调试版需导出数据后卸载安装。
- 前端类型检查及生产构建通过；后端 50 项测试通过。

未新增 Windows 安装/卸载、Linux 原生图形桌面及 Android 真机 VPN 的人工验收。Windows EXE 未签名。签名密钥及密码不进入仓库。
