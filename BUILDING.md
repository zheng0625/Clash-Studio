# 从源码构建 / Building from source

Android 已接入 ARM64 代理内核和 VPN，使用独立 Android Studio 工程构建。见 [Android 工程](android/README.md) 和 [真机验收](docs/Android真机后端验收-2026-10-26.md)。

目标为 Windows x64 与 Linux x64。依赖锁文件见 `frontend/pnpm-lock.yaml`、`src-tauri/Cargo.lock`、`requirements.txt`。

## 准备源码和资源

```sh
git clone https://github.com/zheng0625/Clash-Studio.git
cd Clash-Studio
pnpm --dir frontend install --frozen-lockfile
```

Git 仓库不含内核和规则数据库。下载对应平台的 v0.5.17 发行包，将 `bin/` 复制到源码目录。Windows 打包还需要将 `licenses/Wintun-LICENSE.txt` 放入 `bin/wintun-package/wintun/LICENSE.txt`。保留 `bin/geodata/source.json` 与四项数据库；数据与摘要必须成套维护。

Mihomo v1.19.33 的平台来源记录见 `bin/source.json`、`bin/linux-core-source.json`；Wintun 来源为 https://www.wintun.net/builds/wintun-0.14.1.zip 。第三方许可见 THIRD_PARTY_NOTICES.md。

## Windows

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

可使用 `--data-dir` 或 `CLASH_STUDIO_DATA` 指定开发数据目录。打包脚本拒绝覆盖已有发行目录；不要复制开发数据、订阅、控制密钥、日志、WebView 缓存或本机工具链。当前打包脚本产品版本为 1.2，构建版本为 1.2.0，后续版本需要同步更新。

公开发行时附带本项目对应源码、Mihomo 对应版本上游源码、许可声明及校验文件。构建通过和设备实际使用验证分别记录，见 [0.5.17 验证说明](docs/validation-0.5.17.md)。

## English

Build the Vue frontend and the Rust desktop binary, then assemble a platform-specific package using the matching Python environment. Windows uses Python 3.12 and MSVC; Linux packages use an Ubuntu 22.04 x64 / Python 3.10 baseline. Copy the matching release's `bin/` resources and retain provenance and license files. Keep personal data and development toolchains out of source and release archives.
