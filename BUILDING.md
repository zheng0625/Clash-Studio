# 从源码构建 / Building from source

当前目标：Windows x64，Python 3.12、Node.js 22 或更新的兼容版本、pnpm 10、Rust/MSVC、Microsoft C++ Build Tools 与 Windows SDK。Rust 和前端依赖由各自锁文件记录。

## 1. 获取源码与 Python 环境

源码目录应放在工作目录下；开发版原生程序会使用**源码目录父级**的 `.venv\Scripts\python.exe`。例如：

```powershell
git clone https://github.com/zheng0625/Clash-Studio.git
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\Clash-Studio\requirements.txt
cd Clash-Studio
pnpm --dir frontend install --frozen-lockfile
```

不要将开发环境、个人 data 或真实订阅加入版本控制。`vendor/app` 为源订阅编辑器的后端快照，其源项目和许可见 THIRD_PARTY_NOTICES.md。

## 2. 准备内核资源

Git 仓库只包含源码。最直接的开发方式是下载本项目对应版本的便携包，将其中 `bin/` 复制到源码根目录，并将 `licenses/Wintun-LICENSE.txt` 保存为 `bin/wintun-package/wintun/LICENSE.txt`。保留 `bin/geodata/source.json` 与四项数据库，摘要必须匹配。

上游资源：

- Mihomo v1.19.33：<https://github.com/MetaCubeX/mihomo/releases/tag/v1.19.33>，使用 Windows amd64 compatible 版本，解压并重命名为 `bin/mihomo-windows-amd64-compatible.exe`。
- Wintun 0.14.1：<https://www.wintun.net/builds/wintun-0.14.1.zip>，使用 amd64 DLL 并保留原始许可证。
- 规则数据库：<https://github.com/MetaCubeX/meta-rules-dat>。本版本记录了随附快照的来源及 SHA-256；更新文件时应同时核对并更新元数据，不能将旧摘要套在新文件上。

## 3. 构建桌面

在配置好 MSVC 的 x64 开发终端中执行：

```powershell
pnpm --dir frontend exec vue-tsc --noEmit
pnpm --dir frontend build
cargo build --manifest-path src-tauri/Cargo.toml --release
```

输出为 `src-tauri/target/release/clash-studio.exe`。运行时必须能定位源码根目录；可设置 `CLASH_STUDIO_ROOT` 为源码绝对路径。运行目录与数据位置不应只读。未签名开发程序的系统提示不代表功能已完成兼容性验收。

`dev-env.ps1` / `build-tauri.ps1` 保留了原本机工具链辅助方式；如果使用系统安装的 Rust，请按以上命令构建，不必复制作者的 `.toolchain`。

## 4. 便携打包

`scripts/build-portable.py` 需要在上述 Python 3.12 venv 中运行，还需要 `packaging`：

```powershell
..\.venv\Scripts\python.exe -m pip install packaging
..\.venv\Scripts\python.exe -B scripts/build-portable.py
```

打包脚本拒绝覆盖已存在的发行目录。公开发行包额外包含第三方许可、来源记录和 Mihomo 对应源码；发布所用文档与许可附件可直接从对应 Release 的 source / licenses 目录核对。不要复制开发 data，尤其不要包含订阅、密码、控制令牌、日志或 WebView 用户目录。

## 网页开发预览

```powershell
..\.venv\Scripts\python.exe -B run.py --no-window
# 另一个终端
pnpm --dir frontend dev
```

网页预览使用浏览器语言回退，不提供 Tauri 原生窗口按钮。使用真实系统代理、TUN 或测速前请检查当前网络环境。

## English summary

Install Python 3.12, Node.js/pnpm, Rust/MSVC, C++ Build Tools and the Windows SDK. Clone the source into a workspace and create `.venv` in the **parent directory** of the repository. Install `requirements.txt`, then run the frontend and Cargo commands above.

Copy the matching release's `bin/` resources for local core execution and retain its licenses. The Git repository excludes binaries and user data. The release includes a portable application, corresponding application source, license notices, and a source archive for the unmodified bundled Mihomo version. Build checks do not replace native desktop, network, or TUN validation.
