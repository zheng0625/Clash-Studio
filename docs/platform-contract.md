# 平台接口与数据路径契约 v1

适用版本：0.5.17。当前交付 Windows x64 便携版、Windows x64 安装版与 Linux x64 包，维护者已完成三个版本的使用验证。Linux 构建基线为 Ubuntu 22.04；macOS 仅保留接口与路径适配，尚未交付发行包。

## 路径

资源根包含 run.py、server、vendor、frontend/dist、bin；业务运行中只读。Tauri 使用 project_root 定位，支持便携目录、CLASH_STUDIO_ROOT、开发目录以及 macOS Resources 候选路径。

数据路径解析顺序：显式 --data-dir > CLASH_STUDIO_DATA > 默认目录。Python 的嵌入式 build_app(resources, data_dir=...) 与 Runtime(..., data_dir=...) 接受显式目录；未传时保留 resources/data，方便隔离调用和旧测试。

| 启动方式 | 默认数据目录 |
| --- | --- |
| Windows 安装版（installed.json） | %LOCALAPPDATA%/ClashStudio |
| 带 portable.json 的便携包 | 资源目录/data |
| Windows 开发运行 | 资源目录/data |
| Linux 非便携 | XDG_DATA_HOME/clash-studio，缺省 ~/.local/share/clash-studio |
| macOS 非便携 | ~/Library/Application Support/ClashStudio |

业务数据库、workspace.json、client-settings.json、proxy-selections.json、routing-mode.json、tray-context.json、desktop-settings.json、代理备份、日志、webview2、运行配置与 GeoData 更新暂存均位于此数据根。proxy-selections.json 按订阅保存手动策略组选择，内核停止时可修改，下次启动恢复仍有效的成员。测速隔离数据位于 probe/data。内置 bin/geodata 作为初始化资源读取。

Rust paths.rs、Python server/paths.py 共同实现契约。Tauri 向后端传入绝对 CLASH_STUDIO_DATA；提权助手通过显式参数接收同一个数据目录，自启与提权重启也带 --data-dir。Python 运行时由 paths::python 集中选择，支持 CLASH_STUDIO_PYTHON；带 portable.json 或 installed.json 时使用包内 runtime/python（Windows 为 python.exe，Linux 为 bin/python3），开发时默认使用源码父目录的 .venv。

## 接口

GET /api/client/platform 返回 schema_version、os、arch、id、capabilities、paths；GET /api/client/info 保持旧字段并附加 platform_info 与 paths。客户端应根据能力而非平台名字决定是否允许操作。

server/platforms.py 统一内核文件定位、平台身份与能力、系统代理/提权/进程管理对象的创建。Windows 内核名保持兼容；Linux 使用 mihomo-linux-amd64/arm64，macOS 使用 mihomo-darwin-amd64/arm64。路径映射不表示内核文件已经随包分发。

| 平台 | 系统代理 | TUN / 权限 | 登录自启 |
| --- | --- | --- | --- |
| Windows | WinINET 备份与按所有权恢复 | 随附 Wintun、按需管理员助手 | 当前用户桌面设置 |
| Linux | GNOME 可用时开启，其他环境使用 TUN 或手动代理 | /dev/net/tun、图形 polkit 认证、仅为 Mihomo 设置网络文件能力 | 当前用户 XDG autostart 条目 |
| macOS | 尚未实现 | 尚未实现 | 尚未实现 |

system_proxy 能力在 Linux 根据 GNOME 环境实际检测。tun、elevation、autostart 在 Windows/Linux 为 true；能力存在不代表权限、动态库或设备必然就绪。core 能力表示支持该平台的接口映射，是否已安装内核由 runtime.installed 反映。未支持的模式返回 501。

## 运行与清理

- Windows 适配位于 proxy.py、elevation.py、windows.py、job.py；Linux 适配位于 gnome_proxy.py、linux_tun.py、linux_auth_agent.py、linux_core.py，以及 Rust 桌面集成模块。
- 登录自启只启动应用，不自动启动订阅内核。Linux 普通内核迁移至 TUN 时需要重启内核并恢复同一订阅的有效节点选择。
- 正常停止恢复本程序拥有的系统代理并关闭受管内核；Linux 后端异常退出时由守护进程通知内核退出并有界清理。
- Windows 安装版卸载保留外置应用数据。不同安装形式迁移前应退出旧版并备份数据；不会自动合并数据目录。

使用说明见 [Linux 指南](linux-preview.md)、[构建指南](../BUILDING.md)，验证范围见 [0.5.17 验证说明](validation-0.5.17.md)。
