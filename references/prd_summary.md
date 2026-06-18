# PRD Summary

This summary compresses the team PRD into the parts useful for operating the Skill.

## Product Positioning

皮皮虾医生（OpenClaw Doctor）is a beginner-friendly AI Agent diagnosis and safe self-healing Skill. It helps non-technical users understand what is wrong, what it affects, and what the safest next step is.

## Target Users

- Primary: non-technical users who cannot read logs, terminal errors, cron/API/token terms, or dependency failures.
- Secondary: technical hobbyists who want quick health checks and repeatable diagnosis records.

## Core Scenarios

| Scenario | User pain | Doctor behavior |
|-|-|-|
| First use | Does not know how to start | Guide through a short onboarding flow |
| Runtime error | Does not understand the error | Diagnose and explain in plain language |
| Repair | Afraid to break things | Classify risk and request confirmation before writes |
| Periodic health | Unsure whether maintenance is needed | Generate a health report and next action |
| Repeated issue | Same issue happens again | Search case notes and prescriptions |

## MVP Scope

P0 for v0.3:

1. Read-only local health check.
2. Skill package structure validation.
3. Error-to-prescription matching.
4. Beginner-friendly diagnosis report.
5. Safety policy for repair confirmation.
6. Case note recording.
7. Case note search.
8. Confirmation-ready repair planning.
9. Feishu message routing contract and local router.
10. Team test checklist.

Defer:

- continuous daemon monitoring
- automatic scheduled alerts
- direct high-risk self-repair
- community/group auto-forwarding
- large-scale 438-fault coverage

## Product Boundaries

Can do:

- diagnose local Agent/Skill/config/log/dependency/auth problems
- explain technical problems in plain Chinese
- suggest safe repair plans
- execute low-risk repairs only after confirmation
- record repair cases for future reuse

Cannot do:

- guarantee zero failures
- repair local hardware, network carrier, or platform outages
- bypass login/captcha/anti-bot/rate-limit protections
- access private data unrelated to diagnosis
- perform destructive changes without explicit approval

## Acceptance Criteria

- Health check returns in normal local projects within 5 seconds unless external checks are explicitly enabled.
- Report includes severity, impact, evidence, prescription, risk level, and next step.
- Prescription matcher returns a useful match for common auth, dependency, path, YAML/JSON, network, Lark, and Skill-structure errors.
- Any write operation follows the safety policy.
- A case note can be recorded after a repair attempt.
- Case notes can be searched by issue keywords.
- Repair plans can be generated without executing repairs.
- Feishu message text can be routed to a local doctor action.
- Smoke tests can be run with one command.
- 14 P0 tests can be verified automatically.
- Health reports include passed checks.
- 73+ prescriptions for common OpenClaw issues.
