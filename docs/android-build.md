# Android Studio 接入与真机验证

以下为 0.5.17-ui.1 的初次验证记录。当前 0.5.18-dev.1 已接入订阅管理与配置编辑，并使用 Gradle 9.8.2，见 [主要功能开发记录](android-features.md)。

2026-10-24 已建立 `android/` 原生 Java / WebView 工程，复用现有 Vue 生产界面，独立于桌面 Tauri / Python 宿主。

## 构建环境

| 项目 | 本次验证版本 |
| --- | --- |
| Android Studio | 2026.2.1 |
| JDK | Studio 内置 JetBrains Runtime 25.0.3 |
| Android Gradle Plugin | 9.2.1 |
| Gradle Wrapper | 9.4.1（校验 SHA-256） |
| compileSdk / targetSdk | 37 |
| Build Tools | 36.0.0 |
| minSdk | 26（Android 8.0） |

上述 AGP / SDK / Gradle 组合符合 [AGP 9.2 官方兼容要求](https://developer.android.com/build/releases/agp-9-2-0-release-notes)。

Android Studio 打开 `android/`，使用内置 JDK，等待 Gradle 同步完成。
前端需已安装依赖；构建任务会执行 Vue / TypeScript 检查、Vite 生产构建及 assets 同步。

```powershell
./scripts/build-android.ps1 -OpenStudio
# pnpm 不在 PATH 时指定路径：
./scripts/build-android.ps1 -PnpmExecutable C:/path/to/pnpm.cmd
```

也可在 `android/` 直接运行 `./gradlew.bat assembleDebug lintDebug`。
输出 `android/app/build/outputs/apk/debug/app-debug.apk`，使用本机 debug 签名。
`local.properties`、IDE 本机设置、JDK 自动下载配置与构建缓存均已忽略。
Windows 中文路径目前使用 `android.overridePathCheck=true`，这是 AGP 的实验性配置，需保留实际构建验证。

## 已验证

- Android Studio 日志确认 Gradle 同步完成；Gradle Wrapper 可启动。
- `assembleDebug` 和 `lintDebug` 成功；lint 为 0 errors、6 warnings，包含依赖版本更新建议、ARM64 配置、WebView JavaScript 和备份策略提示。
- APK 已通过 ADB 安装到 PJE110，Android 16 / API 36，`arm64-v8a`，物理分辨率 1264 × 2780。
- 真机执行 9 项检查：五个主页面布局与切换、系统返回主页、键盘视口缩小、返回关闭弹窗、系统文件选择器打开及取消。验证采用实际 ADB 触控与返回键，并读取应用 WebView 状态。
- WebView 可视高度从 859 CSS px 缩小至 547 CSS px；页面没有横向溢出，Dock 保持悬浮液态玻璃效果。
- 返回键先收起软键盘，再关闭导入弹窗；修复了状态栏重叠、原生和 CSS 安全区重复、未知检测时间显示 `Invalid Date` 的问题。
- 验证期间未发现应用 JavaScript 异常或当前进程的 `FATAL EXCEPTION`。
- 文件选择器只验证了打开和取消，未宣称订阅文件解析或导入可用。

工作区 `artifacts/android-device/` 保存测试脚本、JSON 结果、应用日志及真实截图。

## 当前限制

这是界面验证 APK，包名为 `studio.clash.android.validation`，不覆盖正式应用。
没有集成 Python 后端、订阅管理后端、Mihomo 或 Android `VpnService`，未实现真实代理联网。
宿主为 Java / WebView，本包没有原生 `.so`；`arm64-v8a` 配置与 ARM64 真机启动不等于完成 ARM64 代理内核集成。
初始化接口提供空数据和明确的未安装 / 未运行状态；未实现操作返回 501，应用不申请网络权限。
后续需要替换 `ValidationApi`，实现原生后端、ARM64 内核、VPN 授权及生命周期，再执行联网和后台运行验收。
