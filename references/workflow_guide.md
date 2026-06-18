# Workflow Guide

This compresses the team full-process guide into operational rules for the Skill.

## Quality Gates

1. **Syntax gate**: scripts must run without SyntaxError.
2. **API gate**: external calls must have timeout or explicit approval flow.
3. **Function gate**: every meaningful behavior needs command output, screenshot, or structured log evidence.

## Engineering Gates

Use these gates before shipping a test package:

1. Run `run_tests.py` for one-command smoke tests.
2. Validate Skill structure.
3. Run read-only health check.
4. Run prescription matcher with known cases.
5. Generate a repair plan for a known prescription.
6. Verify case recording and case search.
7. Verify Feishu message routing.
8. Zip package and run `unzip -t`.
9. Remove `.DS_Store`, `__MACOSX`, temporary auth images, `__pycache__`, and unrelated files.

## Adaptive Health Rule

- Baseline: compare current score to recent similar checks when case history exists.
- Current score below baseline by 15 or more: downgrade to "report only" until user confirms repair.
- Current score above baseline by 10 or more: record positive lesson.

## Anti-Hallucination Rules

- Prefer real file lists from `rg --files` or structured checks.
- Do not claim a file exists before verifying it.
- Do not claim a repair worked before rerunning a check.
- If evidence is incomplete, say what is unknown.
- Stop after repeated failed repair attempts and generate a fallback report.

## Skill Encapsulation Rule

When a repeated repair requires 5 or more tool calls, mark it as a candidate prescription:

```text
[可封装]
触发场景：
症状：
诊断：
安全修复：
验证方式：
```

---

## 上线部署检查清单

> ⚠️ Agent 接入本 Skill 到目标环境时，必须执行以下检查。

### 前置检查（已完成）

以下为 v4.0 发布前已完成的检查，接入者无需重复：

| 检查项 | 状态 |
|--------|:----:|
| 环境配置参数检查 — 健康评分 100/100 | ✅ |
| 三级功能审计 — 语法/API/功能门全通过 | ✅ |
| 多环境验证 — 三环境功能一致 | ✅ |
| 回滚预案验证 — zip 恢复 < 30 秒 | ✅ |

### 目标环境配置（接入者执行）

| 检查项 | 说明 |
|--------|------|
| [CHECK-19] 监控告警规则 | 为目标环境配置健康检查和失败通知 |
| [CHECK-22] 生产环境部署 | 将 zip 解压到目标路径，运行 `run_tests.py` 确认 |

### 监控告警规则规范

**健康检查探针**：
```bash
# 建议定时执行（每日一次）
python3 <deploy_path>/scripts/doctor_check.py \
  --target <deploy_path> \
  --check skill,tool,system \
  --format json
```
告警条件：`score < 80` 或 findings 中包含 `fail` 级别条目。

**错误通知**：
- 守护进程或定时任务检测到连续执行失败时触发
- 阈值：连续失败达到设定次数
- 动作：降级为只读报告，停止自动修复

**审计**：
- 所有修复操作写入 `.doctor/cases/`
- 周期复查频率：上线首周每日，稳定后每周
