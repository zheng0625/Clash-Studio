# 平台接口与数据路径契约 v1

本轮是跨平台准备，不表示已有可发布的 Linux/macOS 客户端。Windows x64 为当前验证平台。

## 路径

资源根包含 run.py、server、vendor、frontend/dist、bin；业务运行中只读。Tauri 使用 project_root 定位，支持便携目录、CLASH_STUDIO_ROOT、开发目录以及 macOS Resources 候选路径。

数据路径解析顺序：显式 --data-dir > CLASH_STUDIO_DATA > 默认目录。Python 的嵌入式 build_app(resources, data_dir=...) 与 Runtime(..., data_dir=...) 接受显式目录；未传时保留 resources/data，方便隔离调用和旧测试。

| 启动方式 | 默认数据目录 |
| --- | --- |
| 带 portable.json 的便携包 | 资源目录/data |
| Windows 当前兼容方式 | 资源目录/data |
| Linux 非便携 | XDG_DATA_HOME/clash-studio，缺省 ~/.local/share/clash-studio |
| macOS 非便携 | ~/Library/Application Support/ClashStudio |

业务数据库、workspace.json、client-settings.json、routing-mode.json、tray-context.json、desktop-settings.json、代理备份、日志、webview2、运行配置与 GeoData 更新暂存均位于此数据根。测速隔离数据位于 probe/data，沿用原目录层级。内置 bin/geodata 仅作为初始化资源读取。

Rust paths.rs、Python server/paths.py 共同实现契约。Tauri 向后端传入绝对 CLASH_STUDIO_DATA；提权助手通过显式参数接收同一个数据目录，自启与提权重启也带 --data-dir。Python 运行时由 paths::python 集中选择，支持 CLASH_STUDIO_PYTHON；Windows 使用 Scripts/python.exe，Unix 使用 bin/python3。

## 接口

GET /api/client/platform 返回 schema_version、os、arch、id、capabilities、paths；GET /api/client/info 保持旧字段并附加 platform_info 与 paths。客户端应根据能力而非平台名字决定是否允许操作。

server/platforms.py 统一内核文件定位、平台身份与能力、系统代理/提权/进程管理对象的创建。Windows 内核名保持兼容；Linux 使用 mihomo-linux-amd64/arm64，macOS 使用 mihomo-darwin-amd64/arm64。路径映射不表示内核文件已经随包分发。

Linux/macOS 的 system_proxy、tun、elevation、autostart 当前为 false；相关运行时模式操作返回 501，避免执行 Windows 变更。core 能力表示支持该平台的接口映射，是否已安装内核仍由 runtime.installed 反映。

## 后续实现点

- Windows 适配保留在 proxy.py、elevation.py、windows.py、job.py 内；后续在 PlatformServices 后挂接 Linux/macOS 代理、权限、生命周期适配器。
- Linux/macOS 自启、系统代理、TUN 权限与原生托盘均需对应系统实机开发和验收。
- 本轮不迁移或删除现有数据，不下载异平台内核，不修改用户自启或系统代理。
