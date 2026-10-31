# 当前开发状态与项目清理

检查日期：2026-10-31。范围为本地 `clashstudio/` 工作区，不代表远程仓库或线上发行包的即时状态。版本信息来自源码与本地记录，没有查询远程 Release。

## 开发进度

| 范围 | 当前状态 | 依据与边界 |
| --- | --- | --- |
| 版本基线 | 产品版本 1.2、程序版本 1.2.0；Android versionCode 7 | 前端 package.json、Cargo.toml、Android Gradle 配置一致；本地发行验证记录见 validation-1.2.md |
| Windows / Linux 桌面 | 已有订阅编辑、模块分流、节点管理、系统代理、TUN、DNS 防泄漏与桌面集成 | 1.2 历史验证与当前代码；本轮没有重新进行系统网络接管实测 |
| Android | 已接入 ARM64 内核、VPN、订阅、节点选择与测速、精确分流及移动布局 | 当前工程与历史真机记录；本轮没有连接设备或重建 APK |
| 最新桌面 UI | 存在 2026-10-31 独立测试构建，默认窗口 840×760，最小 720×520，含订阅卡片缩放修复 | artifacts/test-builds/1.2-ui-window-20261031/BUILD-REPORT.json；该报告明确未启动原生窗口进行验收 |
| 最新 Android UI | 源码包含布局工坊、规则分页、卡片宽度、状态栏与图标、节点列表底部等多轮调整 | CHANGELOG.md“未发布”；不能据此将各轮改动视为已随正式 1.2 发布 |
| 第一轮内存优化 | 已有缓存、轮询、分页、释放路径和私有工作集口径修正；仍属部分完成 | memory-optimization-implementation-2026-10-29.md；未完成完整 Release A/B、长期堆收敛及全部平台验收 |
| RAM 深度优化 | 专项方案待实施 | runtime-ram-lightweight-plan-2026-10-29.md；轻量模式与服务拆分不能记为已完成 |

工作区有大量既有修改和未跟踪源码，尚未形成一个干净的 Git 检查点。本次保留这些修改，没有提交或重置文件。Android README 仍保留 0.5.18-dev.3 标题及部分历史功能描述，与当前 1.2.0 配置存在文档滞后，后续应按代码与真机验收结果统一。

## 本次验证

| 检查 | 结果 |
| --- | --- |
| 父目录 .venv/Scripts/python.exe -B -m pytest clashstudio/tests -q -p no:cacheprovider | 125 项通过，21.65 秒；1 条 Starlette TestClient/httpx 依赖弃用提醒 |
| pnpm --dir clashstudio/frontend test | 19 项通过 |
| pnpm --dir clashstudio/frontend exec vue-tsc --noEmit | 通过 |
| pnpm --dir clashstudio/frontend exec vite build --outDir 系统临时目录 | 通过；保留原 frontend/dist，构建仅提示输出目录位于项目外 |

上述命令从项目父目录执行。当前轮次没有重跑浏览器视觉回归、Rust 测试、Android Gradle 构建或 Windows/Linux/Android 原生联网测试；历史报告与本次结果分别记录。

## 清理结果

永久删除命令被自动安全检查拦截，随后改用 Windows 回收站完成可恢复清理。

- 共移出项目目录 7,512 个文件，逻辑大小 3,698,325,891 字节，约 3.44 GiB；文件位于回收站，不能将该数值当作磁盘实际释放量。
- 清理 Python `__pycache__` 与 `.pytest_cache`，包括历史源码暂存目录中的一处字节码缓存。
- 清理 Rust release 下 `.fingerprint`、`build`、`deps`、`examples`、`incremental`。
- 清理 Android `.gradle` 和 app、lifecycle-probe、vpn-probe 的 `generated`、`intermediates`、`tmp`。
- 保留 Rust 最终 EXE/PDB、Android outputs/reports/test-results、frontend/dist、依赖与工具链、内核与 GeoData、用户 data、发行包和独立测试包。
- 保留历史操作文档、补丁、备份、UI 工坊、截图和布局导出；没有充分证据证明这些文件已失去用途。

所有目标删除前均检查为项目内目录，不含 Git 跟踪文件或重解析点。保留的 Rust EXE 清理前后 SHA-256 相同：`976e775320088ebdf6899395e717d7cd8e4975c67c896f71908105af4768c86b`。逐目录数量与大小见 `../test-output/cleanup-20261031.json`。首次重新构建 Rust/Android 时将重建中间文件。

## 后续重点

1. 对最新 Windows 测试包进行原生窗口缩放、托盘、UAC/TUN、DNS 与系统代理恢复验收；近期 Android 布局在真机复核。
2. 补齐 Release 内存 S0–S7、长时间堆与监听器收敛、大配置压力及跨平台回归，验证后再宣称内存下降比例。
3. 整理未发布变更和 Git 检查点，更新滞后的 Android 文档；继续拆分主组件及整理样式覆盖顺序。
