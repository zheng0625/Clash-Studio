# Clash Studio v0.5.17 · Windows / Linux

**以可视化订阅编辑、模块化管理和精准分流为核心，结合 Liquid Glass 风格、悬浮 Dock 与可定制主题的 Mihomo 桌面客户端。**

## 精准分流，保留核心能力

按域名、域名后缀、进程名、进程路径及 IPv4 / IPv6 网段构建可复用模块，指定策略组与出口；支持排序、启停、合成预览和严格出口审查。通过真实连接的规则命中和策略链核对分流效果。源订阅与个人修改分开管理，保留可视化编辑、发布、YAML 导出和历史恢复。

## 界面与本版改进

- Liquid Glass 风格层次、悬浮 Dock、统一卡片与设置弹窗；浅色 / 深色主题、自定义配色、照片背景、预览和裁切。
- 提醒水平居中显示于 Dock 上方。
- **主内核停止时可选择手动策略组节点**，按订阅保存，下次启动自动应用。
- **节点点击即时反馈**，同组连续点击合并提交，减少全量刷新和卡片重复渲染。
- Linux 支持 TUN 图形授权、GNOME 系统代理、桌面 Logo 和登录自启；包含此前节点 DNS 引导修复。

## 下载

| 附件 | 用途 |
| --- | --- |
| `ClashStudio-0.5.17-portable-windows-x64.zip` | Windows 便携版；完整解压后运行 ClashStudio.exe |
| `ClashStudio-0.5.17-setup-windows-x64.exe` | Windows 当前用户安装版 |
| `ClashStudio-0.5.17-linux-x64-preview1.tar.gz` | Linux x64；完整解压后运行 ./Start.sh，Ubuntu 22.04 基线 |
| `ClashStudio-0.5.17-source.zip` | 对应应用源码、文档与许可 |
| `mihomo-v1.19.33-source.tar.gz` | 随附 Mihomo 对应版本的上游源码 |
| `SHA256SUMS.txt`、各包 `.sha256` | 校验文件 |

三个应用发行包与维护者已验证的本地包字节一致。维护者已确认三个版本的使用验证；自动检查包括两端各 50 项后端测试、前端检查、Rust 测试及构建、真实打包内核代理、Windows 安装卸载、Linux 原生启动、自启与 TUN 回归。范围详见 [验证说明](https://github.com/zheng0625/Clash-Studio/blob/v0.5.17/docs/validation-0.5.17.md)。

Windows 需要系统 WebView2，包未签名；Linux 需要 GTK/WebKit 等桌面库，详见 [Linux 指南](https://github.com/zheng0625/Clash-Studio/blob/v0.5.17/docs/linux-preview.md)。内置 Python、Mihomo 和四项基础规则数据库，Windows 另含 Wintun。无代理服务或可用订阅。

升级前退出旧版并备份数据。Windows 安装版数据位于 `%LOCALAPPDATA%\ClashStudio`，便携版与 Linux 包默认使用程序旁 `data/`；安装版卸载保留外置数据。登录自启只启动应用，不自动启动订阅内核。Linux 文件名保留 preview1 标记。

项目代码 GPL-3.0-only；第三方组件与数据保留各自许可，见 LICENSE 与 THIRD_PARTY_NOTICES.md。精准分流受接管范围、进程识别及网络环境影响；不保证固定公网 IP，不提供内核退出后的防火墙断网保护。

感谢 Clash Subscription Studio、Tauri、Clash / Dreamacro、Mihomo / MetaCubeX、Clash Verge Rev、Vue、Vite、Lucide、Python、FastAPI、WireGuard / Wintun、meta-rules-dat、Loyalsoldier、v2fly、MaxMind 及其他上游贡献者。本项目独立开发，与上述项目无官方隶属或背书关系。

**English:** v0.5.17 brings offline manual node selection, faster selection feedback, Windows portable and installer packages, and a Linux x64 package. Precise routing and visual subscription editing remain the core, complemented by a Liquid Glass inspired interface, floating Dock and customizable appearance. The three application assets are identical to the locally verified packages. Corresponding sources and SHA-256 checksums are attached. See the README and validation notes for requirements and scope.
