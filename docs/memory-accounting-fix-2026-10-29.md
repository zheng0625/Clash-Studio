# RAM 显示口径修正与验证

日期：2026-10-29。状态：源码修正、Windows 系统采样核验、单元测试与前端构建通过；用户现有测试包需重新构建后才包含本次修改。本次未替换或重启正在使用的应用。

## 问题原因

用户截图显示软件 RAM 459.9 MB、任务管理器应用分组 175.7 MB。原软件主读数使用各进程 Working Set 合计，包含共享页；任务管理器常用内存列使用私有工作集，部分 Windows 版本为活动私有工作集。原明细中的 415.7 MB 为私有提交量，包含未驻留分配，也不能用于对照 RAM。

不同进程的共享页可能重复计入工作集合计。工作集合计既不是进程树去重后的物理内存，也不是任务管理器的默认内存列。不能把这次主读数降低解释为节省了对应数量的内存。

参考：[Microsoft 内存口径说明](https://blogs.windows.com/msedgedev/2021/01/13/investigate-microsoft-edge-memory-usage/)。

## 修正

- Windows 主读数与分类明细改为私有工作集；保留工作集和提交量作为单独诊断指标。
- 资源 API 保留原 `total_bytes`、`bytes`、`method=working_set_sum` 等含义，新增 `private_working_set_total_bytes`、分类 `private_working_set_bytes`、状态和不可读计数，以及主显示口径 `ram_method`。
- 优先读取 `PROCESS_MEMORY_COUNTERS_EX2.PrivateWorkingSetSize`；旧系统回退到 EX 和有界 `QueryWorkingSet` 页查询，按 Shared 位排除共享页。回退最多三次，缓冲上限 32 MiB。
- 私有工作集无法读取时标记缺失或部分数据，不用工作集或提交量补数；真实零值可正常显示。
- Linux 保留原 RSS 主读数及匿名驻留诊断口径，旧后端仍显示工作集并明确说明。
- 明细解释应用进程树/受管理内核的统计范围。任务管理器应用分组、活动状态、采样时刻、权限与四舍五入仍可能造成差异，不承诺数值逐字一致。

API 依据：[扩展内存计数结构](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex2)、[QueryWorkingSet](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-queryworkingset)、[页 Shared 位定义](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-psapi_working_set_block)。

## 实机只读采样

未启动/停止代理、未修改用户配置。对运行中的同一 ClashStudio.exe 进程树进行了两轮相近时间采样；两次都有 9 个进程，窗口和内存会随操作变化，不作为同时刻完全一致的断言。

| 采样来源 | 工作集合计 | 私有工作集合计 | 私有提交合计 |
| --- | --- | --- | --- |
| 本次 Python/PSAPI 采样，字节换算为 MiB | 467.4 | 167.2 | 403.1 |
| 独立 Windows 性能计数器 Win32_PerfRawData_PerfProc_Process | 470.5 | 169.9 | 405.8 |

这组数据支持截图差距主要来自统计口径，不能用旧工作集读数判断 WebView 独占了同等数量的 RAM。UI 沿用历史 MB 单位标记，按 1024² 换算。

## 实际执行的验证

| 检查 | 结果 |
| --- | --- |
| Python 全量测试 `..\.venv\Scripts\python.exe -B -m pytest tests -q` | 125 passed；1 条已有 Starlette 弃用警告 |
| 前端 `pnpm --dir frontend check` | 19 项测试通过，类型检查与 Vite 构建通过；存在 Tauri 模块混合导入提示 |
| Windows 自进程私有工作集与旧页查询交叉验证 | 通过，允许采样期间小幅变动 |
| 缺失/部分/零值、指标隔离、页查询 Shared 位及分配上限回归 | 通过 |

未执行新发行包构建和任务管理器 UI 的同步截图验收；旧 Windows 兼容路径通过模拟回归，未在旧设备上实测。浏览器端已有响应式逻辑回归与构建验证，本次未执行完整浏览器交互验收。
