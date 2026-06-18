# 皮皮虾医生 快速上手指南

```bash
# 1. 结构校验
python3 scripts/doctor.py validate --target .

# 2. 体检（当前目录）
python3 scripts/doctor.py check --target . --format markdown

# 3. 药方匹配
python3 scripts/doctor.py match --text "missing_scope docx:document:readonly"

# 4. 修复计划
python3 scripts/doctor.py plan --text "rm -rf /"

# 5. 病历记录
python3 scripts/doctor.py record --case-dir .doctor/cases --title "问题标题" --status fixed --summary "怎么了"

# 6. 病历搜索
python3 scripts/doctor.py search --case-dir .doctor/cases --query "关键词"

# 7. 飞书路由
python3 scripts/doctor.py route --text "皮皮虾医生 体检" --format json

# 8. 集成测试
python3 scripts/doctor.py test --target .
```
