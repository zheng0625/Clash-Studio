# Clash Studio 1.1

产品版本 1.1，程序版本 1.1.0，Android versionCode 6。

- Windows x64：安装版 EXE、便携版 ZIP。
- Linux x64：Ubuntu 22.04 基线的完整 tar.gz。
- Android arm64-v8a：Release APK；本地开发密钥签名，与本轮设备安装使用相同签名。
- 另附对应源码 ZIP、文件清单及 SHA-256 校验和。

本版包含桌面与手机 UI 优化、完整配置回滚、可取消生命周期任务、配置缓存、共享采样、出口失效处理及 Android 高频存储拆分；修复真机验收发现的旧服务销毁误取消和停止后排队测速复活问题。

Windows 安装包未做代码签名，需要系统 WebView2。Linux 需要 GTK/WebKit 桌面依赖。构建与平台验证范围见 [1.1 验证记录](docs/validation-1.1.md)，Android 故障验收见 [设备记录](docs/Android真机后端验收-2026-10-26.md)。

1.1 发布包可从 GitHub Releases 下载。
