# Output Formats

## JSON Output (check)
```json
{
  "target": "/path/to/target",
  "score": 85,
  "status": "需要处理",
  "scoring_formula": "Health Score = max(0, 100 - fail_count × 22 - warn_count × 10 - info_count × 2)",
  "severity_counts": {"fail": 0, "warn": 1, "info": 2},
  "baseline": {"status": "not_configured", ...},
  "findings": [...],
  "passed_checks": [...]
}
```

## JSON Output (match)
```json
{
  "query": "user error text",
  "matches": [{"score": 100, "matched": ["rx-id"], ...}]
}
```

## JSON Output (route)
```json
{
  "intent": "health_check",
  "action": "run_health_check",
  "command": ["python3", "scripts/doctor.py", "check", "--target", "."],
  "confirmation_required": false,
  "reply_hint": "返回皮皮虾医生健康报告。"
}
```
