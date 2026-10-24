# Linux x64 版 0.5.17-preview1

Ubuntu 22.04 x64 基线构建，附带 Python、业务依赖、Mihomo 和四项 GeoData；不需要 Node 或单独安装 Python。Linux 桌面系统仍需提供 GTK/WebKit 等动态库。

在 Ubuntu 桌面终端安装依赖：

```sh
sudo apt update
sudo apt install libwebkit2gtk-4.1-0 libayatana-appindicator3-1 librsvg2-2
```

依据：[Tauri 官方 Linux 依赖说明](https://v2.tauri.app/start/prerequisites/#linux)。请先完整解压 tar.gz，在解压目录执行 `./Start.sh`。不要使用 root/sudo 启动桌面程序。退出可使用托盘菜单或 `./Stop.sh`。

默认数据保存在解压目录 data；也可执行 `./Start.sh --data-dir "$HOME/.local/share/clash-studio"`。检查 data/startup.log 与 data/tauri-backend.log。

目前 Linux 版提供订阅导入、编辑、分流、节点测速、Mihomo 代理端口和规则/全局/直连模式。GNOME 桌面已支持系统代理接管，配置 HTTP/HTTPS/SOCKS，并在停止和退出时恢复原设置；其他程序改动代理时保留备份且不覆盖。系统代理只影响遵循桌面代理设置的应用，终端 curl 等应用通常需显式传入代理地址。非 GNOME 环境可使用 TUN 或手动配置 HTTP/SOCKS 地址 127.0.0.1:17890。GNOME 托盘显示可能需要 AppIndicator 扩展；WSLg 通常不提供完整状态栏宿主。

## Linux TUN 与登录自启（0.5.14）

在「设置与日志 → 代理设置」选择 TUN，然后应用并启动。第一次可先点「请求管理员权限」：通过 Clash Studio 的图形 polkit 认证窗口，仅为本包的 Mihomo 文件授予 `cap_net_admin,cap_net_raw,cap_net_bind_service=ep`，主窗口和 Python 服务保持普通用户权限。0.5.15 会为本次请求注册进程级认证代理，远程会话启动的应用也能弹出窗口，不依赖所属会话已有认证代理或终端。密码直接交给 PolkitAgent.Session，不经过前端或后端接口，也不保存。

Linux 需要 `/dev/net/tun`、pkexec、setcap，以及系统 Python 的 GTK/Polkit GI 绑定；Ubuntu GNOME 通常已有。缺失时可安装 `sudo apt install pkexec libcap2-bin python3-gi gir1.2-polkit-1.0 gir1.2-gtk-3.0`。取消授权或授权失败时不切换原内核。普通内核切换 TUN 时会重启内核以取得新权限，现有连接可能中断。

文件能力会保留到下次启动；重新解压、复制或升级内核后通常需重新授权。文件系统必须支持 Linux capabilities，不能位于禁止能力生效的挂载点。可用 `getcap bin/mihomo-linux-amd64` 检查；完全退出后，可手动执行 `sudo setcap -r bin/mihomo-linux-amd64` 撤销。不要为 Python 或桌面程序授予文件能力。TUN 停止时关闭网卡和自动路由；普通用户守护进程在后端异常退出时通知内核退出，并进行有界清理。

在桌面设置打开「开机自启」，程序写入当前用户的 `$XDG_CONFIG_HOME/autostart/studio.clash.desktop.desktop`，未设置 XDG_CONFIG_HOME 时使用 `~/.config/autostart/`。这是登录图形桌面后启动，不是登录前的系统服务。保留当前可执行文件与数据目录，开启后台驻留时隐藏至托盘；关闭开关会移除该条目，不影响其他应用。重新移动程序后，请在新位置启动一次以更新已开启的条目。自启不会自动启动订阅内核，网络接管仍需主动开启。

## 0.5.15 桌面与提醒

操作提醒水平居中，位于应用底部 Dock 上方，随 Dock 实际高度及窗口尺寸调整，较长错误信息可换行。Linux 启用 GTK 应用 ID，并为当前用户注册带软件 Logo 的桌面条目与图标，供 GNOME/Wayland Dock 识别。程序正常启动会刷新条目的当前路径；不会因此启用登录自启。

Linux TUN 使用独立的 `198.19.0.0/16` fake-IP 池，避开常见上游路由器的 `198.18.0.0/16` 池，并启用 HTTP/TLS/QUIC 域名识别，避免双层 fake-IP 发生映射冲突。该默认值不等于自动检测所有上游地址池；如果上游也使用 198.19/16，仍需调整上游配置。

0.5.16 为缺少节点专用 DNS 的 Linux TUN 配置补充独立的 `proxy-server-nameserver`，使用阿里 DNS 与 DNSPod DoH，避免节点域名依赖尚未建立的代理或不可达的订阅 DNS 回退链。显式配置的节点 DNS 保留；只更改生成的运行配置，不改源订阅。Linux 保存手动节点选择和 fake-IP 映射；普通内核切换 TUN 重启时，对同一订阅恢复仍有效的手动策略组选择。

虚拟机建议验收：启动浅色界面、导入示例/真实订阅、启动内核、手动代理连通性、节点选择和测速、三种路由模式、编辑保存、重启持久化、关闭和托盘驻留、退出后无残留服务。示例节点不能代理真实网络。

0.5.13 修复：界面平台名称按实际系统显示，隐藏不适用的 Windows 驱动提示；原生托盘实时跟随应用语言（中文、英文及跟随系统），并持久保存；GNOME 下从主窗口或托盘开启代理时自动设置系统代理，停止/退出时恢复之前的设置（原先关闭则恢复关闭），无需进入网络设置手动操作。TUN 与登录自启已在后续版本开放，使用方式见上文。

历史 WSL 验证：Ubuntu 22.04.5 x64，32 项 Python 测试、3 项 Rust 测试通过；打包后的独立运行时完成本机 HTTP 代理请求、规则/全局/直连、托盘接口启停和正常退出。WSLg 实际创建桌面窗口，前端完成 desktop_ready 桌面接口调用，单实例退出成功。以上不替代 Ubuntu 虚拟机中的视觉、GNOME 托盘与真实订阅联网验收。

实际联网测试示例：导入可用订阅、启动内核并选择节点后，在终端执行 `curl --proxy http://127.0.0.1:17890 https://example.com`。若修改了代理端口，请替换命令中的端口。报告问题时附上 Ubuntu 版本、桌面环境、错误提示以及 data 下的日志；分享前检查并删除订阅凭据。

如遇虚拟机图形加速问题，可临时在终端用 `WEBKIT_DISABLE_COMPOSITING_MODE=1 ./Start.sh` 对比定位，不建议默认设置或关闭沙箱。

## 0.5.17 节点选择与切换

主内核停止时可以选择手动策略组节点，按订阅保存，下次启动自动应用。点击立即显示选中态，同组连续点击合并提交。维护者已确认本版本三个发行包的使用验证；自动化范围见 [验证说明](validation-0.5.17.md)。
