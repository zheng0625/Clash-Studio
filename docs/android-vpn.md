# Android ARM64 内核、VPN 与测速 · 0.5.18-dev.3

日期：2026-10-24。测试设备为无线 ADB 连接的 PJE110（Android 16 / API 36，ARM64）。
Android Studio 工程保持在 `android/`，使用其 JBR 25 和项目 Gradle Wrapper 构建。

## 实现

- 固定 Mihomo v1.19.32，libmihomo-android v0.3.11，JNI bridge ABI 3。
- `CoreRuntime` 串行管理初始化、配置应用、节点切换、路由模式、停止与测速内核所有权。
- `ClashVpnService` 管理系统 VPN 授权后的前台服务、TUN fd、通知停止和系统撤销清理。
- gVisor 用户空间协议栈转发 TCP / UDP；核心出站 socket 由 VpnService.protect 防止回环。
- `/runtime/proxies`、`/runtime/connections`、`/network/traffic` 返回真实内核数据。
- 订阅版本检查、运行订阅删除保护、选择失败回滚，GLOBAL 选择持久化。
- 代理端口只绑定回环；禁用导入配置中的控制器、任意监听和桌面 TUN，Provider 路径限制在应用私有目录。
- DNS 覆写与 IPv6 设置在重新应用后生效，Fake-IP 映射保存在私有缓存中。
- 节点 HTTP 延迟测速支持运行内核与按需回环内核两条路径，不伪造延迟值；不可达返回 null。
- 测速内核无 VPN 接口，空闲两分钟显式释放监听及连接。停止后的流量累计冻结，不混入后续测速。
- 前端继续使用原有五项液态玻璃 Dock，实际模式显示 Android VPN；隐藏桌面管理员 / Wintun 流程。

首次 VPN 授权已由设备用户在系统对话框确认；代码通过 VpnService.prepare 检查，并处理取消。
前台类型使用 systemExempted：Android 官方将已配置 VPN 应用列为适用条件。
Manifest 仅对这一服务抑制 Lint 的 exact-alarm 权限误报，不添加无关闹钟权限。
参考：[Android VPN](https://developer.android.com/develop/connectivity/vpn)、
[前台服务类型](https://developer.android.com/develop/background-work/services/fgs/service-types#system-exempted)。

## zcode 合并

已阅读并合入 `zcode操作/0.5.18-安卓测速-操作记录.md` 所列六个文件的测速改动。
保留原始快照；在工作树上补齐 `/api/client/probe/prepare`、测速 Provider 目录与选项保存、
已保存节点选择在内核启动后的恢复、测速失败清理、停止后的计数冻结。
没有执行快照中的全文件覆盖脚本来覆盖后续修复。

真机发现 Mihomo v1.19.32 的 `listener.Cleanup()` 只关闭 TUN，
所以仅调用 JNI `stopListener` 或 `stopTun` 不足以释放 mixed 监听。
现在先把 mixed-port 设为 0 并让内核重建监听，再关闭 TUN / 连接。
参考：[固定版本 listener 源码](https://github.com/MetaCubeX/mihomo/blob/v1.19.32/listener/listener.go)。

Mixed 协议栈在本机回归中出现不稳定，安卓当前固定使用通过真机回归的 gVisor。
不将桌面 TUN 的权限与网卡配置直接移植到安卓。

## 验证与复现

- `assembleDebug`、前端 vue-tsc / Vite、22 项 JVM 测试通过。
- Lint：0 errors，8 warnings；警告包括 JavaScript WebView、备份规则、只打包 ARM64、开发兜底文本和静态上下文检查。
- APK 签名检查通过；仅包含 arm64-v8a 的 libclash.so / libmihomo-jni.so，两者 PT_LOAD 均为 16 KiB 对齐。
- `scripts/verify-android-vpn.cjs` 使用独立 UID 测试 APK，验证 VPN、UDP DNS、HTTPS、真实计数、REJECT、
  规则 / 直连 / 全局、GLOBAL 选择、活动订阅保护、重新应用、前台服务、实际 UI 与停止 / 重启。
- 额外使用仅绑定开发机 127.0.0.1 的 CONNECT 测试代理，经临时 ADB reverse 接到手机，
  验证实际 HTTP 代理节点测速、不可达节点、参数 / 版本错误、界面测速及 VPN 经真实代理节点 HTTPS 联网。
- 两分钟空闲测试检查原有回环端口是否仍返回 HTTP，不能只看 UI 的 running=false。

测试只创建并删除自己的临时订阅，不使用用户付费节点账号。结束时停止测试 VPN 并移除临时 ADB 转发。
独立测试应用按需通过 `-PincludeVpnProbe=true` 构建，不打入主 APK。
主回归脚本的结果与截图输出到指定的 `ANDROID_TEST_OUTPUT` 目录。

当前主 VPN 真机回归 15 项全部通过，包括停止后的 mixed 端口释放。
真实代理节点及测速回归 12 项全部通过，包括实际等待两分钟后确认端口释放。
另验证 IPv6 关闭后，测试 UID 的 IPv6 路由返回不可达，不绕过 VPN 落回底层网络。
总计 22 项 JVM 单元测试、28 项真机检查通过；已清理临时测试订阅、辅助测试应用和 ADB 转发。
APK 大小 19,226,883 字节，versionCode 4，SHA-256：
`f350d6a0bc5b183f74b676adf40a395a94f22c51ea3b7ad9ad41a5b39cc5b519`。
通知栏的应用通知及停止按钮需要系统允许通知；当前设备未授予该权限，
前台服务及 VPN 系统指示仍正常，已验证应用内停止按钮。

## 固定依赖与边界

AAR SHA-256：`01bc41748840c8200bbaf08c044ba8704e35303a3179b75a3cce8517c8944251`。
库源码提交：`5acd6a9ebf7946e18c8f0feaf8302fedf4ebb17d`。
源码与构建方法：[libmihomo-android 固定提交](https://github.com/oviron/libmihomo-android/tree/5acd6a9ebf7946e18c8f0feaf8302fedf4ebb17d)。
Gradle 自动下载并核对固定哈希；GPL 与 Apache 许可和来源记录随 APK 提供。

当前是开发包，尚未验收长期待机、蜂窝/Wi-Fi 切换、全部协议与机型兼容性。
不支持分应用 VPN、Always-on / 开机启动、自动刷新、模块、AI 或订阅发布服务。
Android 13+ 可绕过私有 IPv4 局域网；较早系统仍通过规则处理局域网流量。
出口 IP 查询暂不返回归属地，不支持外部文件路径 Provider。
