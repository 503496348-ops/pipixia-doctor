# Findings — OpenClaw Doctor v5.0 实施发现记录

> PRD 第十章交付物 #4
> 创建日期：2026-06-08

## v5.0 关键发现

### [2026-06-08 17:25] v4.0 实施 vs PRD v3.0 严重不完整（用户审计）

**发现**：v4.0 实施只完成 PRD v3.0 设计内容的 34%（3.42/10 分）。

**关键偏差**：
- P0-2 HEARTBEAT 主动预警：0% 实施（完全缺失）
- P0-4 PCEC 自愈引擎：30% 实施（仅生成计划，未执行）
- 8 个交付物只完成 2 个（25%）

**根因**：v4.0 没有对应的 PRD 文档，导致实施时缺乏对齐参照。

**对策**：用户决策"b/a/a"——合并版 PRD + L0 严格保守 + HEARTBEAT 新通道。

**来源**：evolution_gate/openclaw_doctor_prd_v3_audit.md

### [2026-06-08 16:30] v0.3.1 secret redaction 回归

**发现**：v4.0 的 doctor_record.py 缺少 v0.3.1 已有的 15 种 secret 脱敏模式。

**影响**：病历可能记录 `Bearer xxx`、`ghp_xxx` 等敏感信息。

**修复**：补回脱敏逻辑（已修复）。

**置信度**：高（手动测试通过 5 种 secret 模式）

### [2026-06-08 16:30] feishu_write_full.py 裸 except 隐患

**发现**：5/18 遗留的 feishu_write_full.py:227 有 `except:` 裸捕获。

**影响**：网络抖动会吞掉所有错误，掩盖问题。

**修复状态**：文件已被清理（自动消失，无需修复）。

**置信度**：高（grep 验证）

### [2026-06-08 16:30] PRD vs 实际实现不一致（band 检查）

**发现**：v4.0 PRD.md 声称"OpenClaw 组件检查（HEARTBEAT/MEMORY/cron/band）"，
但 doctor_check.py 实际未实现 band 检查。

**修复**：在 check_openclaw_workspace 中加 band 健康检查（按需触发，不强制要求）。

**置信度**：高

### [2026-06-08 16:30] validate_skill.py description 阈值回退

**发现**：v0.3.1 修过 description 阈值 80→50，v4.0 又改回 80。

**影响**：长 description 的 skill 容易被误判。

**修复**：改回 50（与 v0.3.1 一致）。

**置信度**：中

### [2026-06-08 16:30] run_tests.py 缺反向 case + 临时目录泄露

**发现**：原 11 项测试都是 happy path，没测失败/边界 case。
`tempfile.mkdtemp()` 创建的目录从不清理（资源泄露）。

**修复**：+2 项反向 case（redact-secret + route-fallback）+ TemporaryDirectory。

**置信度**：高

### [2026-06-08 16:30] 8 点推送的 cron 配置与实际行为不一致

**发现**：cron 任务"晨间进化报告"（0 8 * * *）配置 `lastDeliveryStatus: not-requested`，
但 main session 拿到 systemEvent 后**自动用 message tool 发群**。

**根因**：AGENTS.md 定时报告章节给 main 自由发挥空间，未强制覆盖默认行为。

**待解决**：用户决策 #3 (HEARTBEAT) 已落地为新通道，main 自由发挥问题需要 AGENTS.md 改造（Week 4）。

**置信度**：高
