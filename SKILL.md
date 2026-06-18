---
name: openclaw-doctor
description: 皮皮虾医生 v5.0 — OpenClaw Agent 自诊断与安全自愈插件。支持体检、看看状态、报错了、出问题了、帮我修一下、自诊断、自愈、药方库、排查、问题排查、系统体检、快速检查、维护、修复指导、诊断报告、安全修复、健康报告、开药方、故障排查、病历搜索、消息路由。
version: 5.0.0
author: 小乖（李渔樵团队）
tags: [openclaw, doctor, diagnosis, self-healing, agent, health-check, prescription]
requires_tools: [read_file, write_file, edit, exec, search_files]
requires_toolsets: [file, terminal]
---

# 皮皮虾医生（OpenClaw Doctor）v5.0

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

# 包装器（非开发者）
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

## 目录结构

```
openclaw-doctor/
├── SKILL.md                       # 主入口（本文件）
├── README.md                      # 快速开始
├── USER_MANUAL.md                 # 小白用户手册
├── QUICKSTART.md                  # 快速上手指南
├── PRD.md                         # 完整产品需求文档
├── RELEASE_NOTES.md               # 发布记录
├── architecture_roadmap.md        # 架构路线图
├── findings.md                    # 审计发现
├── progress.md                    # 进度记录
├── setup.sh                       # 安装脚本
├── .hermes-skill/                 # Hermes 兼容插件元数据
│   ├── plugin.json
│   └── marketplace.json
├── agents/                        # 角色定义
│   ├── diagnosis-agent.md
│   ├── repair-agent.md
│   └── case-agent.md
├── references/                    # 参考文档
│   ├── prescriptions.md           # 90+ 药方库
│   ├── safety_policy.md           # 安全策略
│   ├── output_formats.md          # 输出格式
│   ├── test_cases.md              # 测试用例
│   ├── prd_summary.md             # PRD 摘要
│   ├── beginner_guide.md          # 小白上手指南
│   └── workflow_guide.md          # 工作流与质量门
├── scripts/                       # 专用脚本
│   ├── doctor.py                  # 统一 CLI 入口（新增）
│   ├── bailongma-doctor           # 包装器（Unix）
│   ├── bailongma-doctor.cmd       # 包装器（Windows）
│   ├── doctor_check.py            # 只读健康检查
│   ├── prescription_match.py      # 药方匹配
│   ├── repair_plan.py             # 修复计划
│   ├── doctor_record.py           # 病历记录
│   ├── case_search.py             # 病历搜索
│   ├── case_verify.py             # 病历校验
│   ├── feishu_route.py            # 飞书消息路由
│   ├── health_maintenance.py      # 日常维护
│   ├── health_score.py            # 健康分基线
│   ├── heartbeat.py               # HEARTBEAT主动预警
│   ├── pcec_engine.py             # 自愈循环引擎
│   ├── redact_release.py          # 发布前脱敏
│   ├── run_tests.py               # 一键集成测试
│   ├── ten_step_method.py         # 锋式十步诊断法
│   └── validate_skill.py          # Skill结构校验
├── skills/                        # 子Skill
│   ├── hermes-check/SKILL.md
│   ├── prescription-match/SKILL.md
│   ├── repair-plan/SKILL.md
│   ├── case-record/SKILL.md
│   ├── case-search/SKILL.md
│   └── feishu-route/SKILL.md
└── .doctor/cases/                 # 病历存档
```

## 安全策略

| 等级 | 操作类型 | 默认行为 |
|------|---------|---------|
| L0 | 只读检查 | 自动执行 |
| L1 | 低风险写入（如补缺失模板） | 先询问 |
| L2 | 中风险（安装依赖/改配置/授权） | 展示影响后询问 |
| L3 | 高风险（删除/覆盖/重置/涉隐私） | 默认不执行 |

> **硬边界**: 不收集 Cookie/Token/密码/私钥，不绕过登录/CAPTCHA/反爬，不静默删除/覆盖/重置。
