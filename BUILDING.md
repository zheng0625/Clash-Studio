# 从源码构建 / Building from source

Android 已接入 ARM64 代理内核和 VPN，使用独立 Android Studio 工程构建。见 [Android 工程](android/README.md) 和 [真机验收](docs/Android真机后端验收-2026-10-26.md)。

目标为 Windows x64 与 Linux x64。依赖锁文件见 `frontend/pnpm-lock.yaml`、`src-tauri/Cargo.lock`、`requirements.txt`。

## 准备源码和资源

```sh
git clone https://github.com/zheng0625/Clash-Studio.git
cd Clash-Studio
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend brand:icons
```

Git 仓库不含内核和规则数据库。下载对应平台的 v0.5.17 发行包，将 `bin/` 复制到源码目录。Windows 打包还需要将 `licenses/Wintun-LICENSE.txt` 放入 `bin/wintun-package/wintun/LICENSE.txt`。保留 `bin/geodata/source.json` 与四项数据库；数据与摘要必须成套维护。

Mihomo v1.19.33 的平台来源记录见 `bin/source.json`、`bin/linux-core-source.json`；Wintun 来源为 https://www.wintun.net/builds/wintun-0.14.1.zip 。第三方许可见 THIRD_PARTY_NOTICES.md。

## Windows

应用品牌图形以 `android/app/src/main/res/drawable/ic_launcher_foreground.xml` 为来源。修改后执行 `pnpm --dir frontend brand:icons`，同步白底黑线 SVG、Windows 多尺寸 ICO、Linux PNG、安卓旧启动器及通知大图；`scripts/make_icon.py` 兼容入口调用同一生成器。安卓通知小图使用透明前景，由系统按通知栏主题着色。

需要 Python 3.12、Node.js / pnpm、Rust MSVC、Microsoft C++ Build Tools 与 Windows SDK。在源码目录**父级**建立 `.venv`：

```powershell
py -3.12 -m venv ..\.venv
..\.venv\Scripts\python.exe -m pip install -r requirements.txt pytest packaging
pnpm --dir frontend build
cargo test --manifest-path src-tauri/Cargo.toml --release
cargo build --manifest-path src-tauri/Cargo.toml --release
..\.venv\Scripts\python.exe -B -m pytest tests -q
..\.venv\Scripts\python.exe -B scripts/build-portable.py
```

Cargo 命令在配置好 MSVC 的 x64 开发终端执行。`dev-env.ps1` 和 `build-tauri.ps1` 是可选的本地工具链辅助入口，使用系统 Rust 时不需作者的 `.toolchain`。程序为 `src-tauri/target/release/clash-studio.exe`；可用 `CLASH_STUDIO_ROOT` 指定源码资源根目录。

安装包由 `scripts/build-windows-installer.py` 从干净便携包生成，使用 Linux / WSL 中的 Python 3 和 NSIS（`makensis`）。脚本中的 `ROOT` 应指向包含 Windows 便携包的源码目录。输出为当前用户安装包；数据位于 `%LOCALAPPDATA%\ClashStudio`，卸载保留数据。

## Linux（Ubuntu 22.04 x64 基线）

需要 Rust、C/C++ 构建工具、pkg-config、Node.js / pnpm、Python 3.10 与 venv，以及 Tauri Linux 开发库：

```sh
sudo apt install build-essential pkg-config python3-venv python3-dev libwebkit2gtk-4.1-dev libayatana-appindicator3-dev librsvg2-dev patchelf
python3 -m venv .venv-linux
.venv-linux/bin/pip install -r requirements.txt pytest packaging
pnpm --dir frontend build
cargo test --manifest-path src-tauri/Cargo.toml --release
cargo build --manifest-path src-tauri/Cargo.toml --release
.venv-linux/bin/python -B -m pytest tests -q
.venv-linux/bin/python -B scripts/build-linux-portable.py
```

Linux `pydantic_core` 等带平台二进制的依赖必须安装为 Linux 对应版本，不要复制 Windows venv。开发运行可设置 `CLASH_STUDIO_PYTHON` 为 `.venv-linux/bin/python` 的绝对路径；也可在父目录建立默认 `.venv`。打包脚本会收集独立 Python 运行时与业务依赖。为减少跨挂载编译问题，WSL 建议在 Linux 文件系统中编译。

运行依赖、图形认证与登录自启说明见 [Linux 指南](docs/linux-preview.md)。不要以 root/sudo 运行桌面程序；TUN 通过图形认证仅赋予内核网络能力。

## 数据与发行

可使用 `--data-dir` 或 `CLASH_STUDIO_DATA` 指定开发数据目录。打包脚本拒绝覆盖已有发行目录；不要复制开发数据、订阅、控制密钥、日志、WebView 缓存或本机工具链。当前打包脚本产品版本为 1.3，构建版本为 1.3.0，后续版本需要同步更新。

公开发行时附带本项目对应源码、Mihomo 对应版本上游源码、许可声明及校验文件。构建通过和设备实际使用验证分别记录，见 [0.5.17 验证说明](docs/validation-0.5.17.md)。

## 更新日志维护

### 独立测试构建

Windows 可在已构建前端和 Rust 程序后，使用独立标签与目录生成测试便携包：

新 UI Windows 测试包先使用 `./build-tauri.ps1 -UiTest` 构建，覆盖配置在 `src-tauri/tauri.ui-test.conf.json`。此选项通过本次进程的 `TAURI_CONFIG` 设置独立应用标识 `studio.clash.desktop.uitest` 和窗口标题；不会更改正式配置。随后使用下方的标签打包方式生成独立便携包。测试数据保存在测试包自己的 `data/` 目录。

```powershell
..\.venv\Scripts\python.exe -B scripts/build-portable.py --label test-20261028 --output-dir artifacts/test-builds/1.2-audit-20261028
```

可用 `--source-archive` 指定已校验的完整对应源码 ZIP。输出目录保留现有文件；不会覆盖已发布的 1.2 包。

Android 使用 `-PacceptanceBuild=true` 构建独立验收包（包名追加 `.acceptance`，本机 debug 签名），可与正式版并存。先完成一次 `pnpm --dir frontend build` 后，可通过 `-x :app:buildFrontend` 复用这一份已验证前端，执行 `:app:assembleDebug :app:testDebugUnitTest :app:lintDebug`。每次构建应检查 APK 内 UI 资源与 `frontend/dist` 的字节一致性，以及 Windows 包中的后端源码与当前 `server/` 的一致性。

每次更新都在 [CHANGELOG.md](CHANGELOG.md) 的“未发布”部分记录内容；发布时整理到对应版本。不要新增独立发布说明文件。源码、Windows 和 Linux 发行包统一附带更新日志。

## English

Build the Vue frontend and the Rust desktop binary, then assemble a platform-specific package using the matching Python environment. Windows uses Python 3.12 and MSVC; Linux packages use an Ubuntu 22.04 x64 / Python 3.10 baseline. Copy the matching release's `bin/` resources and retain provenance and license files. Keep personal data and development toolchains out of source and release archives.
