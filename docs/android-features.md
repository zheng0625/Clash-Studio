> 此文记录 dev.1 订阅功能阶段；dev.3 的内核、VPN 与测速进展见 [Android VPN 开发记录](android-vpn.md)。

# Android 主要功能第一阶段 · 0.5.18-dev.1

2026-10-24，在原生 Android Studio 工程中增加实际的订阅存储与配置处理，替换只读 UI 验证接口。

## 行为

支持 HTTPS Clash YAML 订阅、UTF-8 文件 / 粘贴导入，手动刷新、改名、删除、节点展示与选择、节点 / 策略组 / 规则编辑、草稿检查和保存、历史恢复、偏好保存与 YAML 导出。示例节点明确不提供代理。

源配置和编辑记录分别保存，刷新重新应用编辑；结构错误、引用冲突和旧版本操作不会覆盖已保存内容。原子写入采用临时文件、文件同步和原子重命名；应用进程重启后重新读取私有存储。历史最多保留五份。

原生消息接口限制页面来源和顶层框架。参照 [AndroidX 原生消息接口](https://developer.android.com/reference/androidx/webkit/WebViewCompat)，在后台线程处理网络和存储，消息回复带请求编号。前端保留桌面接口路径，桌面程序继续使用原有 Tauri 后端。

配置解析采用 SnakeYAML 2.7 的 SafeConstructor，限制 8 MB、嵌套、别名展开、节点 / 策略组 / 规则数量。HTTPS 下载验证系统证书，不接受明文 HTTP、嵌入用户名密码或降级重定向；不记录订阅 URL 和源内容到日志。文件导入与导出使用系统文档选择器，无需共享存储权限。

配置检查目前只覆盖结构和引用；真正运行前仍需 Mihomo 校验。内核、VPN、测速、Provider 加载、模块、AI 预设、自动刷新、发布 / 局域网共享服务尚未接入，相关按钮隐藏或禁用。保存端口和 DNS 偏好不会启动监听或修改系统网络。

## 构建与验证

- Android Studio 2026.2.1、JDK 25.0.3、AGP 9.2.1、SDK 37 / Build Tools 36.0.0。
- Wrapper 更新到 Gradle 9.8.2。原 9.4.1 的 Windows 非 ASCII 路径测试工作进程编码缺陷，见 [Gradle 官方修复记录](https://github.com/gradle/gradle/issues/30304)。保留中文源码目录，无需移动用户文件或改变系统区域设置。
- `assembleDebug`、`testDebugUnitTest`、`lintDebug` 组成统一构建入口。
- 13 项 JVM 单元测试通过：持久化、响应隔离、引用改名、历史恢复、无效编辑 / 刷新回滚、版本冲突、节点选择、规则顺序、非法 YAML / 标签 / 别名、循环引用、偏好和损坏存储保护、API 参数 / 来源限制，以及 Activity 宿主重新初始化时避免旧状态覆盖。
- ADB 当时连接 Android Studio 的 API 37 x86_64 模拟器，ARM64 手机已断开。本轮模拟器结果不能代替 ARM64 真机联网验收。
- 12 项原生接口集成检查通过，包括真实 HTTPS 公共演示订阅导入与刷新、文件内容导入、编辑、节点选择、历史恢复、强制停止再启动后的数据与偏好恢复，以及 Vue 节点列表 / 编辑器接入。
- 原生系统文件保存器完成导出，并逐字节验证 UTF-8 文件内容；测试文件已删除。
- 原生接口检查确认内核仍为未安装 / 未运行，未实现的启动请求返回 501。
- 集成测试只创建并清理测试订阅，恢复原偏好，不删除已有订阅，不更改设备代理。

工作区 `artifacts/android-device/features-results.json` 和 `export-results.json` 保存结果；`features-proxies.png` 为使用实际原生数据的模拟器截图。
APK 输出为 `android/app/build/outputs/apk/debug/app-debug.apk`，本地 debug 签名，独立测试包名 `studio.clash.android.validation`。

运行方式见 [Android 工程说明](../android/README.md)。
