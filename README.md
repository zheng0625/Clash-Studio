<p align="center"><img src="frontend/src/assets/brand.svg" width="84" alt="Clash Studio"></p>
<h1 align="center">Clash Studio</h1>
<p align="center">定义新时代 Clash 客户端，让流量分配更精准，让日常使用更舒适。</p>
<p align="center"><a href="https://github.com/zheng0625/Clash-Studio/releases/tag/v1.0">下载 Windows / Linux / Android 版</a> · <a href="README.en.md">English</a> · <a href="docs/project-statement.md">项目声明</a> · <a href="LICENSE">GPL-3.0</a></p>

**Clash Studio 是一款以可视化订阅编辑、模块化管理和精准分流为核心，兼顾界面设计与日常操作体验的 Windows / Linux Mihomo 桌面客户端。**

将源订阅、个人修改、分流模块与内核运行配置衔接起来：先整理节点、策略组和规则，再把不同域名、应用进程与 IP 网段的流量交给指定出口。界面采用 Liquid Glass 风格的层次、悬浮 Dock 与统一卡片布局，让复杂配置拥有清晰的操作入口。

![Clash Studio 0.5.17 概览，使用演示配置，公网信息未查询](docs/screenshots/overview.png)

## 精准分流：让每条规则都有明确去向

- **按域名、域名后缀、进程名、进程路径、IPv4 / IPv6 网段匹配**，为每个模块指定策略组或出口。
- **模块化组合**：在不同订阅方案中复用模块，分别启停、调整顺序；模块规则优先于源订阅规则。
- **严格出口审查**：检查可见的嵌套策略链，拒绝可达 DIRECT、缺失或循环引用，以及无法完整检查的动态成员。
- **结果可核对**：在连接页查看 Mihomo 实际命中的规则、策略链与流量，检查分流是否符合预期。

![模块化精准分流](docs/screenshots/routing-modules.png)

“精准”指通过明确匹配条件与规则优先级控制已被内核接管的流量。实际覆盖取决于系统代理、TUN、进程识别和网络环境；严格审查不保证固定公网 IP，目前不提供内核退出后的防火墙断网保护。

## UI 设计：清晰的信息层级，统一的桌面体验

- **Liquid Glass 风格与悬浮 Dock**：半透明层次、圆角卡片和轻量阴影组织信息，底部导航连接概览、订阅、分流、代理、连接与配置工作台。
- **配色与照片背景**：浅色 / 深色主题、自定义配色、全窗口照片背景、裁切与预览，以及背景明暗和面板参数调整。
- **统一设置交互**：配色、背景与详细参数使用独立弹窗；操作提醒水平居中显示于 Dock 上方。
- **即时节点反馈**：点击立即更新选中态，同组连续点击合并提交，减少全页等待与重复渲染；主内核停止时也能提前选择节点。
- **中文与英文**：支持简体中文 / English，默认跟随系统；页面按需加载，窗口与本地服务并行启动。

![外观与主题设置](docs/screenshots/appearance.png)

## 订阅编辑：刷新来源，保留自己的修改

基于 [Clash Subscription Studio](https://github.com/zheng0625/clash-subscription-studio) 的订阅编辑能力：

- 导入 URL / YAML，编辑节点名称与启用状态、策略组成员与顺序、分流规则。
- 源订阅与个人修改分开保存，刷新后重放修改，并显示冲突与校验结果。
- **草稿 → 预览 → 保存发布 → 应用内核**，修改过程可检查；支持 YAML 导出与历史恢复。
- 手动策略组的节点选择按订阅保存，下次启动自动应用；自动策略组继续由内核选路。

![可视化配置工作台](docs/screenshots/configuration-workbench.png)

## Windows 与 Linux

| 能力 | 当前实现 |
| --- | --- |
| Windows 网络接管 | 系统代理、TUN，按需请求管理员助手 |
| Linux 网络接管 | GNOME 系统代理、TUN；通过图形认证为随附内核授予网络能力 |
| 桌面集成 | 托盘、后台驻留、登录自启；Linux 注册软件 Logo 与桌面入口 |
| 节点管理 | 停止时选节点、单节点 / 整组 / 全部 HTTP 延迟测速；独立测速按需启动 |
| 网络概况 | 实时速率、累计接管流量、活跃连接、公网 IP 与近似归属地 |
| Clash 设置 | 代理端口、局域网连接与可选认证、IPv6、DNS 覆写、GeoData 更新 |

## 下载与使用

当前发布：**1.0 正式版**（构建版本 `1.0.0`），提供 Windows、Linux 与 Android 安装包。构建与检查范围见 [验证说明](docs/validation-1.0.md)。

| 平台 / 形式 | 下载 | 数据目录 |
| --- | --- | --- |
| Windows x64 便携版 | [ZIP](https://github.com/zheng0625/Clash-Studio/releases/download/v1.0/ClashStudio-1.0-portable-windows-x64.zip) | 程序旁 `data/` |
| Windows x64 安装版 | [EXE 安装包](https://github.com/zheng0625/Clash-Studio/releases/download/v1.0/ClashStudio-1.0-setup-windows-x64.exe) | `%LOCALAPPDATA%\ClashStudio` |
| Android arm64-v8a | [APK](https://github.com/zheng0625/Clash-Studio/releases/download/v1.0/ClashStudio-1.0-android-arm64-v8a.apk) | 应用私有目录；旧调试版需先导出配置并卸载 |
| Linux x64 | [tar.gz](https://github.com/zheng0625/Clash-Studio/releases/download/v1.0/ClashStudio-1.0-linux-x64.tar.gz) | 程序旁 `data/`，可用 `--data-dir` 指定 |

Windows 便携版完整解压后运行 `ClashStudio.exe`；安装版运行 EXE 安装包。Linux 完整解压后执行 `./Start.sh`，依赖、TUN 授权与自启说明见 [Linux 使用指南](docs/linux-preview.md)。Linux 包采用 Ubuntu 22.04 x64 构建基线。

内置 Python、Mihomo v1.19.33 和四项基础规则数据库，Windows 另含 Wintun。Windows 需系统已有 [WebView2 Runtime](https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution)；Linux 需桌面 GTK / WebKit 动态库。无需安装 Python、Node 或 Rust。订阅额外引用的远程 Provider / 规则集仍需联网获取。本软件不提供代理服务或可用订阅。

首次使用：导入订阅 → 在配置工作台编辑并保存发布 → 组合分流模块 → 选择节点和接管模式 → 启动内核，在连接页核对结果。登录自启只启动桌面应用，不自动开启订阅内核。

升级前退出旧版并备份数据，避免同时运行多个版本。安装版与便携版使用不同的数据位置，跨形式迁移时需自行备份和迁移。Windows 安装包未签名；兼容性仍会随设备、发行版、桌面环境和节点而变化。

## 开发与项目结构

技术栈：**Tauri 2 / Rust + Vue 3 / TypeScript / Vite + Python 本地配置服务 + Mihomo**。

```text
frontend/       桌面界面、可视化编辑器与语言资源
src-tauri/      原生窗口、IPC、桌面集成与生命周期
server/         配置合成、模块分流、内核运行与平台集成
vendor/app/     Clash Subscription Studio 后端源码快照
tests/          配置、节点选择、运行与平台测试
scripts/        构建、打包与验证工具
licenses/       第三方许可和来源记录
```

构建见 [BUILDING.md](BUILDING.md)。仓库不提交用户数据、订阅凭据、内核二进制或本机工具链；Release 提供应用对应源码、Mihomo 上游源码附件及 SHA-256 校验文件。

## 许可证与项目声明

项目代码采用 **GNU General Public License v3.0（SPDX: GPL-3.0-only）**，见 [LICENSE](LICENSE)。第三方组件、运行库和规则数据库保留各自许可，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。软件按原样提供，不附带担保。

Clash Studio 是独立社区项目，与 Tauri、Clash、Mihomo 或 Clash Verge Rev 不存在官方隶属或背书关系。项目定位、设计原则与能力边界见 [项目声明](docs/project-statement.md)。

## 致谢

感谢 [Clash Subscription Studio](https://github.com/zheng0625/clash-subscription-studio)、[Tauri](https://github.com/tauri-apps/tauri)、Clash / Dreamacro 及其贡献者、[Mihomo / MetaCubeX](https://github.com/MetaCubeX/mihomo)、[Clash Verge Rev](https://github.com/clash-verge-rev/clash-verge-rev)，以及 Vue、Vite、Lucide、Python、FastAPI、WireGuard / Wintun、MetaCubeX/meta-rules-dat、Loyalsoldier、v2fly、MaxMind 等开源项目与数据贡献者。
