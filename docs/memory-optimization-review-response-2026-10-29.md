# 内存优化复核响应（2026-10-29）

状态：复核提出的 R1–R4 已修复并补回归；M01 采样口径、M02 非概览曲线、可还原基线已补齐。Windows Release S0–S7、retained heap、原生托盘/测速/平台验收仍未完成。本文不把浏览器 DOM 结果当作总内存降幅。

## 1. R1：连接缓存清理未受采样锁保护

**修复：** `server/runtime.py` 的应用、内核退出、停止路径统一调用 `invalidate_connections()`，在 `sample_lock` 内清空 `_connection_sample/_connection_wire/_connection_session/_connection_at`。锁序仍为 `lifecycle_lock → sample_lock → client_lock`，没有给采样路径反向加 `lifecycle_lock`。`connection_json` 在锁内再次检查样本非空，异常情况下返回空连接数组而不是 JSON `null`。

**回归：** `tests/test_memory_lifecycle.py::test_stop_waits_for_connection_encoder_and_does_not_repopulate_wire`。让编码线程停在最后一次存活检查，另一线程执行 `_stop_locked`；断言停止线程必须等待编码完成、返回对象不是 null、停止后 `_connection_wire` 没有被重新填回。旧实现会在该交错下失败。

## 2. R2：300 张卡片预算在 16 组以上失效

**修复：** `frontend/src/ProxyPanel.vue` 改为严格分配：用 `min(300, 组数 × 100)` 作为总槽位，基础份额向下取整、余数给前几组；超出预算的组得到 0 个槽位并显示“已达到同时显示上限”。不再保留“每组最低 20 项”。

**回归：**

- 组件脚本：16 组 ×100 → 300；30 组 ×100 → 300；400 组 ×5 → 300，其中 100 组为 0 槽位。
- 真实浏览器（`ui-memory.html`，16 组 ×100）：`.proxy-node-card` = 300；全部折叠 = 0；展开 1 组 = 100；全部展开 = 300；分页文本“每页最多 19 项”。

## 3. R3：缓存等待队列没有本地预算

**修复：** `server/cache.py` 新增 `CacheBusy`、`max_admission_waiters`（默认 8）、`max_waiters`（默认 16）、`wait_timeout`（默认 30 秒）；旁路构建也受构建信号量约束；统计新增 `admission_waiters`/`max_admission_waiters`、等待者上限与超时。超限或超时由 API 映射为 503“配置合成繁忙，请稍后重试”。同键 single-flight、异常传播、版本键与返回副本隔离保持不变。

**回归：** `tests/test_memory_cache.py` 新增 3 项：旁路准入等待有界且计数正确；同键等待者有界；同键等待超时抛 `CacheBusy`。原 single-flight/异常/淘汰/超大项测试仍通过。

**边界：** 同步缓存不支持取消已经开始的构建；请求取消只停止等待，构建会继续完成并写入缓存。这是有意的 single-flight 行为，文档中已写明，不声称“可取消构建”。

## 4. R4：编辑器卸载后仍调度预览

**修复：** `frontend/src/ConfigEditor.vue` 增加 `disposed`；卸载时使代次失效、清空 pending、清除 timer；`checkDraft` 在入口、结果写入和 finally 调度三处都检查 `disposed`。

**回归：** `frontend/tests/memory-frontend.cjs::config editor stops preview scheduling after unmount`。先制造脏草稿、启动一个阻塞预览、再形成 pending，调用卸载回调后释放第一请求；断言 API 调用仍为 1 次、没有新 timer。

## 5. M01 采样与角色

- `server/resources.py` 角色拆分为 `desktop / webview / service / core / probe / other`；主内核与测速内核按受管理 PID 区分；仍保留工作集和私有提交字段。
- UI 明细按平台显示“私有提交合计”或“匿名驻留合计”；零进程角色不显示。
- `scripts/measure-memory.ps1` v2：记录 `created_at`；支持 `-CoreProcessIds` 补录树外受管理内核；主/测速内核按命令行区分；按“每次采样的角色总量”计算 median/p95，而不是把各进程中位数相加；仅保留每 tick 角色总量，结束时不 `Import-Csv` 全量回读。
- 恢复规则：`-CoreProcessIds` 仅在该 PID 当前仍是 mihomo 时纳入；PID 复用可由 `created_at` 识别。

## 6. M02 与重复目录请求

- 非概览页不再累积 60 秒曲线 `samples`；回到概览立即采样。
- 代理目录增加 5 秒复用窗口，显式刷新、配置版本变化、订阅切换仍强制拉取。浏览器实测代理页 6.2 秒目录请求从 4 次降到 2 次。

## 7. 可还原基线

复核指出原检查点只有哈希。本轮用“反向已知补丁 + 检查点 SHA-256”重建全部 13 个被修改文件，再补入其余 149 个未变文件：

- 目录：`artifacts/memory/baseline-source-20261029/`
- 压缩包：`artifacts/memory/baseline-source-20261029.zip`
- 全量校验：`MANIFEST-verified.txt`，**162/162 文件大小与 SHA-256 完全匹配**
- 复现脚本：`scripts/rebuild-memory-baseline.py`、`scripts/reconstruct-frontend-baseline.py`、`scripts/write-baseline.py`、`scripts/write-frontend-baseline.py`、`scripts/complete-baseline.py`

这不是“当前候选另存为基线”：每个被修改文件都通过识别反向替换重建，并逐字节命中原检查点哈希；包括 `cache.py` 末尾混合换行和 `ConfigEditor.vue` 多余空行这类 1 字节差异。

## 8. 浏览器验收

`docs/memory-validation-2026-10-29.md` 与 `artifacts/memory/browser-validation-20261029.json` 记录了 16 组 ×100 节点、5,000 连接的 Dev Vite 页面：

- 300 卡片、折叠 0/单组 100、搜索节点 99 得到 16 项
- 连接 100 行、搜索 1/5000、暂停/恢复文案
- 离页 6.2 秒 `/connections` 增量 0；带 `host-4999` 筛选离开再返回后仍为 1 行、筛选值保留
- 概览流量 6/6.2 秒、代理页 2/6.2 秒
- 隐藏 5.2 秒内流量与内存请求增量均 0，恢复后 0.6 秒内 +1
- 内存明细显示桌面宿主/WebView/本地服务/主内核与私有提交合计

限制：Dev Vite、非 Release、无 retained heap、无原生窗口隐藏、5,000 而非 20,000 连接、未执行节点选择写回。

## 9. 仍未完成

- Windows Release S0–S7 三次独立启动、预热/稳定窗口、集成 A/B、CPU/交互 p95
- retained heap / detached DOM / 监听器收敛
- 20,000 连接、2,000 节点/30,000 规则浏览器压力
- M08 测速 TTL/Timer/目录实验；M09 托盘轻量入口/WebView2 挂起；M10 桥接；M11 外观
- Linux / Android 平台回归；TUN/DNS/系统代理恢复
- 摘要/完整载荷分离与服务端连接分页（按测量门槛保留）

## 10. 结论

R1–R4 已修复并有针对性回归；M01/M02 的采样缺口已补；基线可逐字节还原；浏览器 DOM 与可见性验收通过。**仍不能声称客户端总内存下降某个百分比或达到 20% 目标**，因为 Release S0–S7 与 retained heap 尚未执行。
