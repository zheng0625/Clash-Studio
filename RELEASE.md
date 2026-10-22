# Clash Studio v0.5.1 · Windows x64 便携测试版

**以订阅可视化修改和模块化管理为核心，让不同应用、域名和网段的流量准确匹配到指定策略组。**

Clash Studio 基于 Clash Subscription Studio 的订阅编辑能力，将源订阅、个人修改、模块分流与 Mihomo 运行管理融合在同一桌面应用中。

## 订阅与精确分流

- 可视化编辑节点、策略组、成员和规则；源订阅与个人修改分开保存，刷新后重新应用修改。
- 按域名、域名后缀、进程名、进程路径、IPv4 / IPv6 网段创建分流模块，为每个模块指定策略组或出口。
- 模块可复用、启停和排序，合成预览后应用；严格审查可见出口链，并通过实际连接的命中规则与策略链核对分流效果。
- 保留草稿、发布、YAML 预览与导出，以及历史恢复能力。

## 本版体验

- Windows 系统代理与 TUN；按需请求管理员助手，主窗口无需重启。
- 单节点、整组与全部节点 HTTP 延迟测速；主内核停止时可按需使用独立测速内核。
- 实时速率、累计接管流量、连接与公网 IP / 近似归属地。
- 自定义代理端口、局域网连接与认证、IPv6、DNS 覆写及 GeoData 更新。
- 自定义配色、全窗口照片背景、预览与裁切。
- 简体中文 / English，默认跟随 Windows 显示语言；入口为“设置与日志 → 设置 → 界面语言”。
- 窗口与本地服务并行启动、加载状态和页面按需加载，减少启动阶段的空白等待。

## 下载与使用

1. 下载 `ClashStudio-0.5.1-portable-windows-x64.zip`，**完整解压**到可写目录。
2. 运行包内 `ClashStudio.exe`，自行导入订阅后使用。
3. 升级前关闭旧版并备份 `data/`，不要同时运行多个版本。

内置 Python、Mihomo v1.19.33、Wintun 和四项基础规则数据库。系统需已有 [Microsoft Edge WebView2 Runtime](https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution)。订阅自身的远程 Provider / 规则集仍需联网，本软件不提供代理服务或订阅。

附件包含 SHA-256 校验文件、Clash Studio 对应源码，以及未修改的 Mihomo v1.19.33 源码。公开发行包保留原便携版可执行程序，补充了公开项目说明、第三方许可、数据归属和源码附件，因此 ZIP 校验值与先前本地测试包不同。

## 状态与边界

这是测试版：已通过类型检查、前端 / Rust 构建与包完整性核对；0.5.1 尚未完成干净 Windows、多语言排版、UAC/TUN 和实际启动耗时的完整实机验收。

精确分流作用于已被内核接管、且能识别匹配条件的流量；不保证固定公网 IP。当前没有内核退出后的防火墙断网保护。未知第三方诊断可能保留原文。

## 许可与致谢

项目源码采用 **GPL-3.0-only**，第三方组件和数据保留各自许可，见仓库 LICENSE 与 THIRD_PARTY_NOTICES.md。

感谢 [Clash Subscription Studio](https://github.com/zheng0625/clash-subscription-studio)、[Tauri](https://github.com/tauri-apps/tauri)、Clash / Dreamacro 及其贡献者、[Mihomo / MetaCubeX](https://github.com/MetaCubeX/mihomo)、[Clash Verge Rev](https://github.com/clash-verge-rev/clash-verge-rev)，以及 Vue、Vite、Lucide、Python、FastAPI、WireGuard / Wintun、meta-rules-dat、Loyalsoldier、v2fly 和 MaxMind 等开源项目与数据贡献者。

---

**English:** A Windows desktop client focused on visual subscription editing, reusable routing modules, and precise domain/process/subnet routing. Extract the full portable ZIP and run `ClashStudio.exe`. Python, Mihomo, Wintun and four base databases are included; system WebView2 is required. Language follows Windows by default and can be changed in Settings and logs. This is a development preview, not a fully validated production release. Project code: GPL-3.0-only; dependencies and datasets retain their own licenses. See the README and bundled notices for attribution and limitations.
