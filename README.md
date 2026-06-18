# 皮皮虾医生（OpenClaw Doctor）v5.0

> 合并自 openclaw-doctor v4.0 + hermes-doctor v0.1.1
> 版本: 5.0.0 | 发布日期: 2026-06-19

## 快速开始

```bash
# 统一入口
python3 scripts/doctor.py check --target . --format markdown
python3 scripts/doctor.py test --target .

# 旧入口（向后兼容）
python3 scripts/doctor_check.py --target . --format markdown
```

## v5.0 增量改进

| 改进 | 来源 |
|------|------|
| 统一 CLI (`doctor.py`): check/match/plan/record/search/route/validate/test | hermes-doctor |
| OpenClaw 深度检查: 系统负载/HEARTBEAT体积/memory/heartbeat文件数/38个Skill完整性 | 审计发现 |
| 系统资源检测: load average, 磁盘提示 | 审计发现 |
| 药方库合并: 90+ 药方（原73+20） | 双源合并 |
| 包装器: bailongma-doctor (Unix + Windows) | hermes-doctor |
| 修复: redact泄漏测试残留 | 审计修复 |
| 新增: HEARTBEAT_OK 格式兼容（支持多种标记格式） | 审计修复 |
| 新增: health_score.py `--target` 参数 | 审计修复 |
| Hermes插件兼容: .hermes-skill/plugin.json | 兼容层 |
| 子Skills: 6个（hermes-check/prescription-match/repair-plan/case-record/case-search/feishu-route） | hermes-doctor |

## 目录结构

见 SKILL.md。
