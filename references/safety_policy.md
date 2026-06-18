# Safety Policy

## Risk Levels

| Level | Meaning | Action |
|-|-|-|
| L0 | Read-only checks and reports | Can run automatically |
| L1 | Low-risk writes | Show path/content summary first |
| L2 | Install/auth/restart/config changes | Show command, impact, verification, rollback, then wait |
| L3 | Delete/overwrite/reset/secret access | Do not execute automatically |

## Risk Matrix

| Level | Definition | Allowed | Confirmation | Forbidden |
|-|-|-|-|-|
| L0 | Read-only checks and reports | Inspect public project files, parse non-sensitive logs, generate reports | No | Read `.env`, cookies, tokens, private keys |
| L1 | Low-risk writes | Write doctor docs, prescriptions, case notes, subskill docs | Yes, show path and content summary | Overwrite business files, write secrets |
| L2 | Install/auth/restart/config changes | Install dependencies, auth login, edit manifest, restart local service | Yes, show command, impact, verification, rollback | Silent execution, external calls without timeout |
| L3 | Delete/overwrite/reset/secret access | Manual plan only by default | Exact action approval required | `rm -rf`, `git reset --hard`, secret reading, bypass login/captcha/rate limits |

## Data Rules

- Do not collect cookies, tokens, passwords, private keys, or unrelated personal data.
- `.env` can be detected but not read or echoed.
- Redact sensitive strings before writing cases.
- Do not bypass login, captcha, anti-bot, or rate-limit protections.
