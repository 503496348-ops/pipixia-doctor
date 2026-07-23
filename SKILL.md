---
name: pipixia-doctor
description: "OpenClaw Agent数字遗产+永恒记忆+复活系统。独立产品，与白龙马医生为同领域不同平台。当需要管理Agent数字遗产、配置永恒记忆、实现Agent复活时使用。"
version: 1.2.0
author: 小乖（李渔樵团队）
tags: [doctor, diagnosis, self-healing, agent, health-check, prescription]
requires_tools: [read_file, write_file, edit, exec, search_files]
requires_toolsets: [file, terminal]

triggers:
  - 智能体健康
  - Agent诊断
  - pipixia
  - 皮皮虾
---

# 皮皮虾医生v5.1

## Sandbox Repair Context（v1.2.0）

## 快速开始

```bash
python3 scripts/doctor.py --help
python3 scripts/cli.py --help
```


新增 `diagnostics/agent_sandbox_repair_context.py`：把沙盒运行时发现转换为可审阅修复动作，区分自动计划、需要确认与阻断项，并把运行上下文合并进病历记录。

皮皮虾医生是一个面向小白用户的 Agent 自诊断与安全自愈 Skill。不是直接替用户乱修，而是先体检、再分诊、开药方，最后按风险等级确认修复。

## 核心工作流

1. **体检（Inspect）**: 只读收集证据。
2. **分诊（Triage）**: 判断严重度、影响范围和风险。
3. **开药方（Prescribe）**: 匹配药方库。
4. **确认（Confirm）**: 写入、安装、授权、重启、删除前确认。
5. **验证（Verify）**: 运行最小验证。
6. **记录（Record）**: 写入脱敏病历。

## When To Use

激活此插件的场景：
- 用户说 `皮皮虾医生 体检`、`看看状态`、`自诊断`、`系统体检`
- 用户贴报错、日志、工具调用失败、配置失败、依赖失败
- 用户说 `帮我修一下`、`自愈`、`怎么修`、`开药方`
- 用户需要查询或写入历史处理记录
- 用户需要路由飞书消息到本地诊断动作

不激活的场景：
- 普通聊天或泛化技术科普
- 需要绕过登录、验证码、反爬或限流保护

## CLI Commands

```bash
# 统一入口（推荐）
python3 scripts/doctor.py check --target . --format markdown
python3 scripts/doctor.py match --text "fetch failed timeout"
python3 scripts/doctor.py plan --text "unknown tool 工具调用失败"
python3 scripts/doctor.py record --title "问题" --status fixed --summary "怎么了"
python3 scripts/doctor.py search --query "fetch"
python3 scripts/doctor.py route --text "皮皮虾医生 体检" --format json
python3 scripts/doctor.py validate --target .
python3 scripts/doctor.py test --target .

# Agent 快照与恢复（v5.1 数字遗产+复活）
python3 scripts/doctor.py snapshot --target . --snapshot-action save --description "版本描述"
python3 scripts/doctor.py snapshot --target . --snapshot-action list
python3 scripts/doctor.py snapshot --target . --snapshot-action verify --snapshot-id snap-XXXX
python3 scripts/doctor.py snapshot --target . --snapshot-action restore --snapshot-id snap-XXXX --dry-run

# 药方自学习（v5.1 智能进化）
python3 scripts/doctor.py learn --target . --learn-action report
python3 scripts/doctor.py learn --target . --learn-action feedback --rx-id RX-XXX --query "错误文本" --outcome miss
python3 scripts/doctor.py learn --target . --learn-action effectiveness
python3 scripts/doctor.py learn --target . --learn-action candidates
python3 scripts/doctor.py learn --target . --learn-action gaps

# 包装器（非开发者）@
scripts/bailongma-doctor check --target .

# 专用脚本（老用户兼容）
python3 scripts/doctor_check.py --target . --format markdown
python3 scripts/prescription_match.py --text "错误信息"
python3 scripts/repair_plan.py --text "问题"
python3 scripts/doctor_record.py --case-dir .doctor/cases --title "问题" --status fixed --summary "怎么了"
python3 scripts/case_search.py --case-dir .doctor/cases --query "关键词"
python3 scripts/feishu_route.py --text "皮皮虾医生 体检"
python3 scripts/validate_skill.py .
python3 scripts/run_tests.py
```

## 文件结构

```
pipixia-doctor/
├── SKILL.md / README.md / PRD.md   # 文档
├── scripts/doctor.py               # 统一CLI入口
├── scripts/agent_snapshot.py       # Agent快照与恢复（v5.1）
├── scripts/rx_learner.py           # 药方自学习引擎（v5.1）
├── scripts/{doctor_check,prescription_match,repair_plan,doctor_record,case_search,feishu_route,validate_skill}.py
├── references/                     # 药方库/安全策略/测试用例
├── skills/                         # 子Skill（hermes-check/prescription-match/repair-plan/case-record/case-search/feishu-route）
└── .doctor/cases/                  # 病历存档
```

## 安全策略

| 等级 | 操作类型 | 默认行为 |
|------|---------|---------|
| L0 | 只读检查 | 自动执行 |
| L1 | 低风险写入（如补缺失模板） | 先询问 |
| L2 | 中风险（安装依赖/改配置/授权） | 展示影响后询问 |
| L3 | 高风险（删除/覆盖/重置/涉隐私） | 默认不执行 |

> **硬边界**: 不收集 Cookie/Token/密码/私钥，不绕过登录/CAPTCHA/反爬，不静默删除/覆盖/重置。


---

## 工作流

- [ ] 1. 确认用户需求和诊断场景
- [ ] 2. 加载Agent配置和运行日志
- [ ] 3. 执行健康诊断（插件/工具/记忆/安全）
- [ ] 4. 生成诊断报告和修复建议
- [ ] 5. 验证修复效果


---

## 技术架构

- **诊断引擎**: 多维度Agent健康检查（插件完整性/工具调用/记忆一致性/安全策略）
- **自愈机制**: 检测→定位→修复→验证闭环
- **数据管线**: 日志采集→模式匹配→异常检测→报告生成
- **API接口**: Python SDK + CLI工具 + Hermes Agent集成

## 2026-07-03 运行时增强

- 新增检索过滤注入探针，拦截未知过滤键、空值和危险过滤片段。
- 验证：新增模块通过 py_compile 和定向 pytest，代码不依赖外部服务。

## 2026-07-03 产品收敛门禁

- 新增 `scripts/product_convergence_gate.py`：从远端干净 clone 后可运行 `python3 scripts/product_convergence_gate.py --json`，检查 SKILL/README、入口文件、smoke 目标、测试与外部融合引用是否自洽。
- 新增 `tests/test_product_convergence_gate.py`：确保门禁在产品仓库中真实可执行，避免后续增强只停留在孤岛模块。

## 一键开箱交付

本仓库提供标准一键入口：

- `install.sh`：用户的一条命令安装与冒烟入口。
- `scripts/setup.py`：安装声明依赖并串联 doctor。
- `scripts/doctor.py`：检查 README、SKILL、入口脚本、package scripts 与产品收敛门禁。
- `scripts/smoke.py`：运行 doctor、产品收敛门禁与 Python 编译级冒烟。
- `tests/test_one_click_open_box.py`：契约测试，防止 README 写了但脚本缺失。


## Lark Coding Agent Bridge 融合增强

- 皮皮虾医生新增 Bridge Repair Advisor：stream idle、workspace missing、Codex JSONL drift、profile crosstalk 修复建议。
- 新增模块：`diagnostics/resurrection_bridge_repair.py`
- 来源模式：飞书/Lark 消息入口、本地 Claude/Codex 执行、会话 fingerprint、profile 隔离与安全门禁。

## Generic orchestration repair plans

Adds deterministic repair planning for drift, stale pending events, poison events, missing flow logs, and broken confirmation states.
