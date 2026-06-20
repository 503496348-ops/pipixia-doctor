# 皮皮虾医生（OpenClaw Doctor）v5.1

> 合并自 openclaw-doctor v4.0 + hermes-doctor v0.1.1
> 版本: 5.1.0 | 品牌: AtomCollide-智械工坊
> 发布日期: 2026-06-20

## 快速开始

```bash
# 统一入口
python3 scripts/doctor.py check --target . --format markdown
python3 scripts/doctor.py test --target .

# 旧入口（向后兼容）
python3 scripts/doctor_check.py --target . --format markdown
```

## v5.1 新增：数字遗产 + 智能进化

### 🗂️ Agent 快照与恢复（数字遗产+复活）

完整捕获 Agent 状态（SOUL/MEMORY/skills/configs），支持版本化快照、差异对比和一键恢复。

```bash
# 创建快照
python3 scripts/doctor.py snapshot --target . --snapshot-action save --description "修复前备份"

# 列出所有快照
python3 scripts/doctor.py snapshot --target . --snapshot-action list

# 对比两个快照
python3 scripts/doctor.py snapshot --target . --snapshot-action diff --snapshot-id snap-A --other-snapshot-id snap-B

# 验证当前状态与快照是否一致
python3 scripts/doctor.py snapshot --target . --snapshot-action verify --snapshot-id snap-XXXX

# 从快照恢复（预演模式）
python3 scripts/doctor.py snapshot --target . --snapshot-action restore --snapshot-id snap-XXXX --dry-run

# 独立脚本
python3 scripts/agent_snapshot.py --target . --mode save --description "备份描述"
```

**核心能力：**
- 快照 = tar.gz 归档 + SHA-256 校验清单
- 自动收集 SOUL.md、MEMORY.md、skills/、memory/、cron/ 等关键文件
- 恢复前自动创建备份（安全回滚）
- 支持 dry-run 预演模式

### 🧠 药方自学习引擎（智能进化）

反馈驱动的药方优化：追踪药方命中率、分析未覆盖错误模式、自动生成候选药方。

```bash
# 完整学习报告
python3 scripts/doctor.py learn --target . --learn-action report

# 记录反馈（药方命中/未命中/有效/无效）
python3 scripts/doctor.py learn --target . --learn-action feedback \
  --rx-id RX-AUTH-001 --query "missing_scope error" --outcome hit --resolved

# 药方效果分析
python3 scripts/doctor.py learn --target . --learn-action effectiveness

# 生成候选药方（从未解决的重复错误中学习）
python3 scripts/doctor.py learn --target . --learn-action candidates

# 药方覆盖率缺口分析
python3 scripts/doctor.py learn --target . --learn-action gaps

# 独立脚本
python3 scripts/rx_learner.py --target . --mode report
```

**核心能力：**
- 追踪每个药方的命中/未命中/有效/无效反馈
- 计算成功率和趋势（improving/declining/stable）
- 从未解决的重复错误中自动聚类生成候选药方
- 从用户手动解决的案例中提取新药方建议

## v5.0 增量改进

| 改进 | 来源 |
|------|------|
| 统一 CLI (`doctor.py`): check/match/plan/record/search/route/validate/test/snapshot/learn | hermes-doctor + v5.1 |
| OpenClaw 深度检查: 系统负载/HEARTBEAT体积/memory/heartbeat文件数/Skill完整性 | 审计发现 |
| 系统资源检测: load average, 磁盘提示 | 审计发现 |
| 药方库合并: 90+ 药方 | 双源合并 |
| 包装器: bailongma-doctor (Unix + Windows) | hermes-doctor |
| Hermes插件兼容: .hermes-skill/plugin.json | 兼容层 |
| 子Skills: 6个 | hermes-doctor |

## CLI 命令总览

| 命令 | 说明 | 风险等级 |
|------|------|---------|
| `check` | 只读健康检查 | L0 |
| `match` | 药方匹配 | L0 |
| `plan` | 修复计划生成 | L2 |
| `record` | 脱敏病历写入 | L1 |
| `search` | 病历搜索 | L0 |
| `route` | 飞书消息路由 | L0 |
| `validate` | 包结构验证 | L0 |
| `test` | 集成测试 (11项) | L0 |
| `snapshot` | Agent快照与恢复 | L0-L3 |
| `learn` | 药方自学习 | L0 |

## 目录结构

见 SKILL.md。

## 竞品对标

| 能力 | 皮皮虾医生 v5.1 | Dify | LangChain | AutoGen |
|------|-----------------|------|-----------|---------|
| Agent健康诊断 | ✅ 深度体检+药方库 | ❌ | ❌ | ❌ |
| 自愈引擎 | ✅ PCEC循环 | ❌ | ❌ | ❌ |
| 数字遗产 | ✅ 快照+恢复 | ⚠️ 版本管理 | ⚠️ 序列化 | ❌ |
| 智能进化 | ✅ 药方自学习 | ⚠️ 标注反馈 | ❌ | ⚠️ 学习循环 |
| 多Agent协同 | ❌ (v6.2规划) | ✅ | ✅ | ✅ |
| 工作流编排 | ❌ | ✅ | ✅ | ✅ |
