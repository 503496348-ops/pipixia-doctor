# Feishu Bot Handler

This file defines the Feishu message routing contract for OpenClaw Doctor. It is not a complete bot server; use it as the integration spec for the real Lark/Feishu event consumer.

## Message Contract

| User message | Intent | Local action |
|-|-|-|
| `皮皮虾医生 体检` | health_check | `doctor_check.py --target .` |
| `皮皮虾医生 看看状态` | health_check | `doctor_check.py --target .` |
| `皮皮虾医生 报错了：...` | prescription_match | `prescription_match.py --text ...` |
| `皮皮虾医生 帮我修一下：...` | repair_plan | `repair_plan.py --text ...` |
| `皮皮虾医生 上次这个问题怎么处理的：...` | case_search | `case_search.py --query ...` |
| `皮皮虾医生 带我上手` | onboarding | read `beginner_guide.md` |

## Local Router Test

```bash
python3 openclaw-doctor/scripts/feishu_route.py --text "皮皮虾医生 报错了：missing_scope docx:document:readonly"
```

Expected:

- intent: `prescription_match`
- action: `match_prescription`
- confirmation: `false`

## Bot Safety Rules

- Do not execute repair commands directly from a group message.
- For `repair_plan`, return the plan first and ask for confirmation.
- If a command needs auth, install, write, delete, overwrite, reset, or external network access, require explicit confirmation.
- Do not echo cookies, tokens, passwords, private keys, or unrelated personal data back to the group.
- If user-provided text contains suspected secret material, redact it before writing a case note.

## Reply Template

```text
皮皮虾医生

识别意图：{intent}
处理结果：{summary}
风险等级：{L0/L1/L2/L3}
下一步：{single action}
```

## Integration Notes

Use the real Feishu event layer only for message receive/send. Keep diagnosis logic inside this Skill package so it can also run locally in tests.

Recommended flow:

1. Feishu event consumer receives a group or private message.
2. Verify the sender and chat are allowed.
3. Pass message text to `feishu_route.py`.
4. Execute only L0 actions automatically.
5. For L1-L3, send a confirmation message before executing anything.
6. Record final result with `doctor_record.py`.
