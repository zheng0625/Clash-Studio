<p align="center"><img src="frontend/src/assets/brand.svg" width="84" alt="Clash Studio"></p>
<h1 align="center">Clash Studio</h1>
<p align="center">定义新时代Clash客户端，让订阅修改更可控，让流量分配更精确。</p>
<p align="center"><a href="https://github.com/zheng0625/Clash-Studio/releases">下载便携版</a> · <a href="README.en.md">English</a> · <a href="LICENSE">GPL-3.0</a></p>

**Clash Studio 是一款以订阅可视化修改、模块化管理和精确分流为核心的 Windows Mihomo 客户端。**

基于 [Clash Subscription Studio](https://github.com/zheng0625/clash-subscription-studio) 的订阅编辑能力，将源订阅、个人修改、分流模块与本机运行配置衔接起来。通过可视化操作整理节点、策略组和规则，再把不同域名、应用进程或 IP 网段交给指定的策略组与出口。

![Clash Studio 0.5.1 概览，公网信息已隐藏](docs/screenshots/overview.png)

## 核心特点

### 订阅修改：更新源配置，也保留自己的选择

- URL / YAML 订阅导入、刷新和本地管理。
- 可视化修改节点名称与启用状态，调整策略组成员、类型和顺序，编辑分流规则。
- 源订阅与修改记录分开保存；刷新订阅后重新应用修改，显示冲突和校验结果。
- 草稿 → 预览 → 保存发布 → 应用内核，修改过程可检查；提供 YAML 导出和历史版本恢复。

![配置工作台](docs/screenshots/configuration-workbench.png)

### 精确分流：将分流意图保存为可复用模块

- 支持**域名、域名后缀、进程名、进程路径、IPv4 / IPv6 网段**等匹配条件。
- 每个模块指定目标策略组或出口，可在不同订阅方案中组合、启停和排序。
- 模块规则优先于源订阅规则；通过规则顺序明确流量去向。
- 严格出口审查检查嵌套策略链，拒绝可达 DIRECT、缺失或循环引用，以及无法完整检查的动态成员。
- 在连接页查看内核实际命中的规则、策略链与流量，核对分流效果。

> “精确”指基于明确匹配条件与规则优先级控制已被内核接管的流量。实际覆盖受系统代理、TUN、进程识别及网络环境影响；严格审查不保证固定公网 IP，目前也不提供内核退出后的防火墙断网保护。

![模块化精确分流](docs/screenshots/routing-modules.png)

### 桌面运行与日常体验

| 能力 | 当前实现 |
| --- | --- |
| 网络接管 | Windows 系统代理、TUN，按需请求管理员助手 |
| 节点测速 | 单节点、整组、全部节点 HTTP 延迟测速；可独立于主内核运行 |
| 网络概况 | 实时速率、累计接管流量、活跃连接、公网 IP 与近似归属地 |
| Clash 设置 | 自定义代理端口、局域网代理与可选认证、IPv6、DNS 覆写、GeoData 更新 |
| 个性外观 | 自定义配色、全窗口照片背景、预览与裁切 |
| 语言 | 简体中文 / English，默认跟随 Windows 显示语言 |
| 启动 | 窗口与后台服务并行启动、加载提示、页面按需加载 |

## 下载与使用

当前发布：**0.5.1 Windows x64 便携测试版**。

1. 打开 [Releases](https://github.com/zheng0625/Clash-Studio/releases)，下载 `ClashStudio-0.5.1-portable-windows-x64.zip`。
2. 将整个压缩包解压到可写目录，运行其中的 `ClashStudio.exe`。
3. 导入自己的订阅，在配置工作台修改并保存，在模块分流页配置精确分流方案。
4. 选择系统代理或 TUN，应用配置并启动内核；在连接页核对命中规则和出口。

便携包自带 **Python、Mihomo、Wintun 和四项基础规则数据库**；不需要安装开发工具。系统需要已有 [Microsoft Edge WebView2 Runtime](https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution)。订阅自身额外引用的远程 Provider / 规则集仍需联网获取。包内不提供代理服务或可用订阅。

界面语言入口：**设置与日志 → 设置 → 界面语言**。数据保存在程序旁 `data/`，升级前请关闭旧版并备份该目录。不要同时运行多个版本。

## 开发与项目结构

技术栈：**Tauri 2 / Rust + Vue 3 / TypeScript / Vite + Python 本地配置服务 + Mihomo**。

```text
frontend/       桌面界面、可视化编辑器与语言资源
src-tauri/      原生窗口、本机 IPC、后台进程生命周期
server/         订阅方案合成、模块分流、内核运行与系统设置
vendor/app/     Clash Subscription Studio 后端源码快照
scripts/        图标、构建与便携打包辅助脚本
licenses/       第三方许可和来源记录
```

构建方式见 [BUILDING.md](BUILDING.md)。本仓库不提交用户数据、订阅凭据、内核二进制或本机工具链。发布标签与源码附件对应当前版本。

## 开发状态

本项目仍处于测试阶段，目前面向 Windows x64。0.5.1 已完成类型检查、前端与 Rust 构建及发布包完整性核对；本次尚未完成干净 Windows、不同系统语言及真实 UAC/TUN 的完整实机验收。已有版本的局部实测不代表所有功能和环境均已通过。

## 许可证与声明

Clash Studio 项目代码使用 **GNU General Public License v3.0（SPDX: GPL-3.0-only）**，见 [LICENSE](LICENSE)。允许按该许可使用、修改与再分发；分发修改版时应遵守相应源码与许可保留要求。软件按原样提供，不附带担保。

第三方组件、规则数据库、字体或运行库保留各自许可，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。Clash Studio 是独立社区项目，与下列项目不存在官方隶属或背书关系。

## 致谢

感谢开源社区提供的基础与灵感：

- [Clash Subscription Studio](https://github.com/zheng0625/clash-subscription-studio)：订阅可视化编辑与源配置、修改记录分离管理的基础。
- [Tauri](https://github.com/tauri-apps/tauri)：桌面应用框架与原生能力。
- Clash / Dreamacro 及其贡献者：Clash 规则、配置格式和代理生态的奠基工作；历史来源可参考 [Mihomo](https://github.com/MetaCubeX/mihomo)。
- [Mihomo / MetaCubeX](https://github.com/MetaCubeX/mihomo)：实际代理、TUN、DNS 与规则匹配内核。
- [Clash Verge Rev](https://github.com/clash-verge-rev/clash-verge-rev)：桌面交互和界面组织的参考。
- [Vue](https://github.com/vuejs/core)、[Vite](https://github.com/vitejs/vite)、[Lucide](https://github.com/lucide-icons/lucide)：界面与开发工具。
- [WireGuard / Wintun](https://www.wintun.net/)、[Python](https://www.python.org/)、[FastAPI](https://github.com/fastapi/fastapi)：系统网络与本地服务能力。
- [MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat)、[Loyalsoldier](https://github.com/Loyalsoldier)、[v2fly/domain-list-community](https://github.com/v2fly/domain-list-community)、[MaxMind](https://www.maxmind.com/) 及其他上游数据贡献者：规则与地理数据库资源。

