# Clash Studio 内存基线（2026-10-29，部分）

状态：已完成**可复现的后端合成基线**与进程采样工具；Windows Release 包 S0–S7 实机基线**未执行**。本文不把合成数据称为客户端内存降幅。

## 1. 源码与检查点

- 工作区父提交：`0989c1ba746a8f43063d6e77d095167e3010a004`（`main`）
- 检查点：`artifacts/memory/checkpoint-20261029/`
- 文件清单：162 个源码文件，`parent_commit / SHA-256 / bytes`
- `SHA256SUMS.txt` 哈希：`3106d2ff8b1fcbfa7b0bc0e8820a6ad7c8750059b3943a5be6a511e47330d3e0`
- **可还原基线**：`artifacts/memory/baseline-source-20261029/` 与 `.zip`（约 407 KB），`MANIFEST-verified.txt` 对 162 个文件逐一校验大小与 SHA-256，**162/162 匹配**。
- 13 个被修改文件由反向补丁重建并逐字节命中原哈希（含 `cache.py` 末尾混合换行、`ConfigEditor.vue` 多余空行等 1 字节差异）；其余 149 个文件复制自当前工作区后逐项校验。重建脚本见 `scripts/rebuild-memory-baseline.py`、`reconstruct-frontend-baseline.py`、`write-baseline.py`、`write-frontend-baseline.py`、`complete-baseline.py`。
- 基线不包含订阅、凭据、用户数据或二进制。

## 2. 环境

| 项 | 值 |
| --- | --- |
| 机器 | Intel Core i5-12400F，15.8 GiB RAM |
| 系统 | Windows 10 专业工作站版 10.0.19045 |
| Python | 3.12.14（`..\.venv`） |
| 输入 | `scripts/benchmark-backend.py` 合成配置，假地址，不联网 |
| 日期 | 2026-10-29 |

## 3. 指标口径

- **后端合成峰值**：`tracemalloc` 在测量区间内的 Python 分配峰值，单位字节。只覆盖 Python 对象，不含 WebView、Mihomo 或 GPU。
- **单次合成耗时**：`time.perf_counter` 中位数，单位毫秒。
- **缓存预算**：16 个不同版本键、8 MiB 上限下的保留条目、估算字节、淘汰数；估算方法为递归 `sys.getsizeof`，不是精确 Python heap。
- **进程采样**（`scripts/measure-memory.ps1`）：按 PID 流式写 CSV，记录工作集与私有提交；预热窗口不计入汇总。权限不足记为不可读，不记零。

## 4. 实测结果（合成，单机）

命令：

```powershell
..\.venv\Scripts\python.exe -B scripts/benchmark-backend.py
```

原始数据：`artifacts/memory/backend-benchmark-20261029/backend-benchmark.json`。

| 场景 | 指标 | 结果 |
| --- | --- | --- |
| 200 节点 / 3,001 规则，未缓存合成 3 次 | 中位耗时 | 2184.6 ms |
| 同上 | tracemalloc 峰值 | 7,014,174 B |
| 同上，缓存冷启动 1 次 | 中位耗时 | 2114.5 ms |
| 同上，缓存热命中 3 次 | 中位耗时 | 2.6 ms（峰值 84,952 B） |
| 5,000 连接，摘要与完整列表各自独立请求（对照） | 耗时 / 峰值 / 传输字节 | 169.9 ms / 5,836,067 B / 1,904,712 B |
| 5,000 连接，共享 0.9 秒快照 | 耗时 / 峰值 / 传输字节 | 61.0 ms / 3,528,715 B / 476,178 B |
| 缓存预算：16 键 / 8 MiB | 保留条目 / 估算字节 / 淘汰 | 8 / 4,177,500 B / 8 |
| 停止后 | 连接对象 / 编码字节 / 会话引用 / 累计流量 | 均已释放 / 保留 |

说明：共享快照与热命中是**既有能力**；移除入缓存前的多余深拷贝后，同一脚本在本机得到共享快照峰值 3,528,715 B，此前一次运行（其他代码相同、保留额外深拷贝）为 5,247,275 B。该对比为单次合成运行，不是 Release 客户端 RSS 降幅。

## 4.1 后端进程单独冒烟（非 Release、非完整应用）

用独立数据目录和 `--no-window` 启动开发后端，未启动内核、未导入订阅；采样器 v2 按每次采样的角色总量统计：

| 角色 | 工作集中位数 | 私有提交中位数 | 说明 |
| --- | --- | --- | --- |
| 本地服务 | 65,589,248 B（62.6 MiB） | 48,087,040 B（45.9 MiB） | API 解释器及 venv 启动器 |
| 其他 | 14,745,600 B（14.1 MiB） | 8,105,984 B（7.7 MiB） | 开发控制台宿主 `conhost.exe`，打包桌面运行时不适用 |
| 桌面宿主 / WebView / 主内核 / 测速内核 | 0 | 0 | 未启动对应进程 |
| 合计 | 80,334,848 B（76.6 MiB） | 56,193,024 B（53.6 MiB） | 含开发控制台宿主 |

原始数据：`artifacts/memory/backend-s0-smoke-v2/samples.csv` 与 `summary.json`。此前的 v1 单进程冒烟（API 64.08 MB / 私有 48.36 MB、启动器 3.55 MB、conhost 14.76 MB）保存在 `backend-s0-smoke/`。Release 包的 WebView、主内核和测速内核均未包含在此数据中。

## 5. 未执行的基线

| 场景 | 状态 | 具体缺口 |
| --- | --- | --- |
| S0 空载 | 未执行 | 未启动 Windows Release 包；没有 WebView/Python/内核的进程归属数据 |
| S1 普通使用 | 未执行 | 需要 200 节点 / 3,000 规则的真实运行配置与独立测试目录 |
| S2 大配置 | 未执行 | 需要 2,000 节点 / 30,000 规则的 Release 实机轮次 |
| S3 连接压力 | 仅合成 | 500/5,000/20,000 条 mock 已完成 5,000 条；20,000 条与切页/暂停/恢复未做浏览器内存采样 |
| S4 托盘后台 | 未执行 | 需要 Windows Release 包与托盘开关 30 次 |
| S5 测速 | 未执行 | 需要受控测速环境；本轮不改测速生命周期 |
| S6 编辑压力 | 未执行 | 仅有单元级副本检查，无 30 次预览/保存的堆数据 |
| S7 稳定性 | 未执行 | 需要 60 分钟后台运行与多轮 retained heap |

缺口原因：当前会话没有可用的 Release 包构建/运行授权窗口，且计划要求不自动启动用户代理、TUN 或真实订阅。未实测平台不得标记为达标。

## 6. 采样工具用法

```powershell
# 自动查找唯一 clash-studio 桌面进程
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/measure-memory.ps1 `
  -DurationSeconds 420 -WarmupSeconds 120 -IntervalSeconds 2

# 指定根进程，并补录树外受管理内核（仅当该 PID 当前仍是 mihomo 时纳入）
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/measure-memory.ps1 `
  -RootProcessId 12345 -CoreProcessIds 22345,22346 `
  -DurationSeconds 420 -OutputPath artifacts/memory/s0-run1
```

输出：`samples.csv`（流式写入）与 `summary.json`（按角色汇总中位数/p95、不可读样本数）。工具自测（对 PowerShell 自身进程树）已在 `artifacts/memory/selftest/` 完成，确认 CSV 与汇总可用。
