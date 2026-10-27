# Clash Studio 1.1 构建与验证范围

产品版本 1.1，程序语义版本 1.1.0；Android versionCode 为 6。Windows 安装版、便携版、Linux x64 包及 Android ARM64 包使用同一份前后端源码。

## 产物

- ClashStudio-1.1-setup-windows-x64.exe
- ClashStudio-1.1-portable-windows-x64.zip
- ClashStudio-1.1-linux-x64.tar.gz（Ubuntu 22.04 构建基线）
- ClashStudio-1.1-android-arm64-v8a.apk
- ClashStudio-1.1-source.zip
- SHA256SUMS-1.1.txt 和 BUILD-REPORT-1.1.json

文件位于项目 `artifacts/releases/`。完整产物清单、字节数、校验和与本次构建检查结果以 `BUILD-REPORT-1.1.json` 为准；未执行的检查不得记录为通过。

## 本版内容

包含桌面与手机 UI 优化、应用完整回滚、生命周期任务取消与队列隔离、版本配置缓存、共享连接采样、出口缓存失效、Android 高频状态存储拆分及稳定错误码。

Android 原生代码还包含真机验收发现的两项修复：旧服务销毁回调不再误取消后续操作；停止后消息桥队列中的过期测速不再继续启动测试内核，系统授权批准也走同一生命周期队列和取消检查。

## 检查依据

- 前端执行 TypeScript 检查与生产构建；桌面分别编译 Windows MSVC 和 Linux 原生 Tauri 程序。
- Python 后端回归及包内 Python/内核回环验证使用隔离数据目录，不修改真实订阅或系统代理。
- Android 执行 Release 构建、JUnit 和 Lint；1.1 的版本号变更之外，相关原生逻辑的 27 项 ARM64 真机验收见 [设备记录](Android真机后端验收-2026-10-26.md)。
- Windows 便携版及 Linux 包内 manifest 记录实际文件校验和。源码包只包含源码、构建描述、测试、许可与文档，不包含开发数据、密钥、日志或本机工具链。

## 签名与安装

本地未配置 Android 正式分发密钥，APK 使用本机 Android 开发密钥签名，Release 模式不启用调试或验收故障读取。与本轮此前安装的 1.0 本机签名包兼容升级；不同签名的历史安装需先导出配置再卸载。Windows EXE 未做 Authenticode 签名，文件完整性用 SHA-256 核验。

Windows 需系统 WebView2；Linux 需 GTK/WebKit 桌面依赖。真实磁盘满、断电、多机型长期后台保活及 Linux/Windows 提权 TUN 迁移不因构建成功而视为完成验收。

本次生成本地产物，不自动上传 GitHub、发布到应用商店或替换用户设备上的安装。
