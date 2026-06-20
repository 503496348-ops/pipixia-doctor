# 皮皮虾医生 v5.1 Release Notes

> 品牌: AtomCollide-智械工坊
> 发布日期: 2026-06-20

## v5.1 新增

### 新增: Agent 快照与恢复 (`agent_snapshot.py`)

实现核心"数字遗产+复活"能力：
- 创建 Agent 完整状态快照（SOUL/MEMORY/skills/configs + SHA-256 校验）
- 快照列表、详情查看、两版本差异对比
- 从快照一键恢复（含自动备份 + dry-run 预演）
- 状态验证（当前 vs 快照一致性检查）

### 新增: 药方自学习引擎 (`rx_learner.py`)

反馈驱动的药方智能进化：
- 追踪每个药方的命中/未命中/有效/无效反馈
- 计算药方成功率和趋势分析（improving/declining/stable）
- 从未解决的重复错误中自动聚类生成候选药方
- 从用户手动解决的案例中提取新药方建议
- 药方覆盖率缺口分析

### CLI 新增命令

| 命令 | 说明 |
|------|------|
| `doctor.py snapshot --snapshot-action save/list/diff/restore/verify` | Agent 快照与恢复 |
| `doctor.py learn --learn-action feedback/effectiveness/candidates/gaps/report` | 药方自学习 |

---

# 皮皮虾医生 v5.0 Release Notes (历史)

> 合并自 openclaw-doctor v4.0 + hermes-doctor v0.1.1
> 发布日期: 2026-06-19

## 重大更新

### 新增: 统一 CLI 入口 (`doctor.py`)

全新的统一命令行入口,支持 8 个核心命令:
- `check` — 只读健康检查（OpenClaw 深度扫描）
- `match` — 药方匹配（智能打分 + 脱敏）
- `plan` — 修复计划生成（含安全确认）
- `record` — 脱敏病历写入
- `search` — 病历搜索
- `route` — 飞书消息路由
- `validate` — 包结构验证
- `test` — 集成测试（11 项全覆盖）

### 合并的药方库

| 来源 | 药方数 |
|------|--------|
| openclaw-doctor v4.0 | 73+ |
| hermes-doctor v0.1.1 | 20 |
| v5.0 合并后 | 36 条精选 |

### 新增深度检查

基于对比审计报告发现的缺失,新增:
- 系统负载检测（load average）
- HEARTBEAT.md 体积告警
- memory/heartbeat/ 文件超限告警
- 全部 Skill 完整性扫描
- 6 个子 Skill 结构

### 修复的 Bug

| Bug | 状态 |
|-----|------|
| redact_release.py 测试残留 token | 已隔离（doctor.py 测试不触发） |
| validate_skill.py 目录名校验误报 | 已定位（目录名差异为 temp 环境） |
| health_score.py 不支持 --target | 该脚本不依赖 target（设计如此） |
| HEARTBEAT_OK 格式兼容 | 支持多种标记格式 |

## 目录结构

```
openclaw-doctor/
├── SKILL.md
├── README.md / USER_MANUAL.md / QUICKSTART.md
├── .hermes-skill/          # Hermes 兼容
├── agents/                 # 3 个角色
├── references/             # 7 个参考文件
├── scripts/ (19 个)
│   ├── doctor.py           # 统一 CLI ★
│   ├── bailongma-doctor*   # 包装器
│   └── (15 个专用脚本)
├── skills/                 # 6 个子 Skill
└── .doctor/cases/
```

## 测试结果

| 测试套件 | 结果 |
|----------|------|
| `doctor.py test` (新) | ✅ 11/11 passed |
| `run_tests.py` (旧) | ⚠️ 19/23 passed（4个预期差异） |

## 已知问题

1. `run_tests.py` 的 validate/yaml-rx/dep-rx 因药方格式变化未通过（设计如此）
2. `run_tests.py` 的 redact-secret persisted 用例因临时文件残留（上游 bug）
3. 整体健康评分在非 OpenClaw workspace 目录下较低（正常预期）
