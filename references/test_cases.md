# Test Cases

## P0

| ID | Command | Expected |
|-|-|-|
| TC-P0-001 | `python3 scripts/doctor.py validate --target .` | `OK` |
| TC-P0-002 | `python3 scripts/doctor.py check --target .` | `皮皮虾医生` |
| TC-P0-003 | `python3 scripts/doctor.py check --target . --format json` | `passed_checks` |
| TC-P0-004 | `python3 scripts/doctor.py check --target /no/such/path` | `RX-FILE-001` |
| TC-P0-005 | `python3 scripts/doctor.py match --text "fetch failed timeout"` | `RX-RUNTIME-001` |
| TC-P0-006 | `python3 scripts/doctor.py plan --text "unknown tool"` | repair plan |
| TC-P0-007 | `python3 scripts/doctor.py route --text "皮皮虾医生 体检" --format json` | `health_check` |
| TC-P0-008 | `python3 scripts/doctor.py test --target .` | all passed |
| TC-P0-009 | `python3 scripts/doctor.py match --text "token=abc123 cookie=xyz"` | `RX-SAFETY-001` |

## Acceptance Gate

- SKILL.md present and valid
- Subskills present
- Health report includes passed checks
- Prescription match covers runtime/tool/safety cases
- Repair plan never executes repair commands
- Case records are redacted
- Health JSON includes scoring_formula, severity_counts, and baseline
- At least 12 prescriptions present
- Wrapper command exists for non-developer usage
