# Linux x64 使用指南 · 0.5.17

Linux 包以 Ubuntu 22.04 x64 为构建基线，文件名保留 preview1 标记。附带 Python、业务依赖、Mihomo v1.19.33 和四项 GeoData，无需安装 Node、Rust 或单独的 Python 环境。

## 安装与启动

Ubuntu 桌面系统需要以下动态库：

```sh
sudo apt update
sudo apt install libwebkit2gtk-4.1-0 libayatana-appindicator3-1 librsvg2-2
```

完整解压 tar.gz 后执行 `./Start.sh`。不要使用 root/sudo 运行桌面程序。退出可使用托盘菜单或 `./Stop.sh`。GNOME 托盘显示可能需要 AppIndicator 扩展；其他发行版需提供兼容的系统库。

默认数据位于解压目录 `data/`。可使用 `./Start.sh --data-dir "$HOME/.local/share/clash-studio"` 指定其他目录。升级前退出旧版并备份数据；不要同时运行多个版本。日志位于数据目录的 `startup.log` 与 `tauri-backend.log`，分享前删除订阅凭据、控制密钥和个人网络信息。

## 订阅、节点与网络接管

导入订阅，在配置工作台编辑并保存发布，再组合分流模块。主内核停止时即可选择手动策略组节点，选择按订阅保存，下次启动自动应用；自动策略组仍由内核选路。点击节点立即显示选中态，同组连续点击合并提交。

节点测速可按单节点、整组或全部执行；主内核停止时按需使用独立测速内核，不开启系统代理或 TUN，空闲两分钟自动退出。使用 Provider 时可先点击“加载 / 刷新 Provider 节点”。测速反映 HTTP 延迟，不代表下载带宽。

GNOME 支持 HTTP/HTTPS/SOCKS 系统代理接管，并在停止或退出时恢复本程序拥有的设置。系统代理仅影响遵循桌面代理设置的应用。其他桌面环境可使用 TUN，或在应用中手动指定 HTTP/SOCKS 地址（默认 `127.0.0.1:17890`）。

## TUN 与图形授权

在概览选择 TUN 模式并启动内核，或在内核运行时切换模式。首次授权使用 Clash Studio 的图形 polkit 窗口，仅为随附 Mihomo 授予 `cap_net_admin,cap_net_raw,cap_net_bind_service=ep`；主窗口和后端保持普通用户权限。远程启动时会注册本次请求的进程级认证代理。密码直接交给 PolkitAgent.Session，不经过前端或后端接口，也不保存。

需要 `/dev/net/tun`、pkexec、setcap 和系统 Python 的 GTK/Polkit GI 绑定；缺失时可安装：

```sh
sudo apt install pkexec libcap2-bin python3-gi gir1.2-polkit-1.0 gir1.2-gtk-3.0
```

取消授权或授权失败会保留原内核。普通内核迁移到 TUN 时需要重启，现有连接可能中断，并恢复同一订阅中仍有效的节点选择。

文件能力在后续启动时保留；重新解压、复制或升级内核后通常需要重新授权。文件系统必须支持 Linux capabilities。可用 `getcap bin/mihomo-linux-amd64` 检查，完全退出后可用 `sudo setcap -r bin/mihomo-linux-amd64` 撤销。不要为 Python 或桌面程序设置这些能力。

Linux TUN 默认使用 `198.19.0.0/16` fake-IP 池，并启用 HTTP/TLS/QUIC 域名识别。如果上游同样使用这个地址池，仍需调整配置。缺少节点专用 DNS 时，生成的运行配置补充阿里 DNS 与 DNSPod DoH 作为 `proxy-server-nameserver`，避免节点域名依赖尚未建立的代理；显式节点 DNS 保留，源订阅不改写。

正常停止会关闭 TUN 与自动路由；后端异常退出时，守护进程通知内核退出并进行有界清理。精确分流依赖流量接管、规则与进程识别，不代表所有应用和网络环境均已覆盖。

## 桌面图标、托盘与登录自启

程序为当前用户注册带软件 Logo 的桌面入口，供 GNOME/Wayland Dock 识别；操作提醒水平居中显示于应用 Dock 上方。托盘语言随应用设置切换。

在桌面设置打开“开机自启”，写入 `$XDG_CONFIG_HOME/autostart/studio.clash.desktop.desktop`；未设置时使用 `~/.config/autostart/`。这是登录图形桌面后启动，不是登录前的系统服务。启用后台驻留时可隐藏至托盘。自启只启动应用，不自动启动订阅内核。

移动程序后，在新位置启动一次以更新已开启的自启条目。关闭开关会移除本应用的条目，不影响其他应用。

## 连通性与排查

应用代理端口测试（替换为实际端口）：

```sh
curl --proxy http://127.0.0.1:17890 https://example.com
```

先核对实际接管模式，再在连接页检查规则、策略链和流量。已有连接可能继续使用原节点，新连接使用新选择。出现虚拟机图形加速问题时，可临时用 `WEBKIT_DISABLE_COMPOSITING_MODE=1 ./Start.sh` 对比，不建议默认启用。

维护者已确认 Windows 便携版、安装版和 Linux 版的使用验证。构建与自动检查范围见 [0.5.17 验证说明](validation-0.5.17.md)，平台与数据路径见 [平台契约](platform-contract.md)，开发构建见 [BUILDING.md](../BUILDING.md)。
