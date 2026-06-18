# 皮皮虾医生 Beginner Guide

欢迎使用皮皮虾医生。

第一步先做只读体检：

```bash
python3 scripts/doctor.py check --target .
```

如果你有报错，把最关键的一两行贴给药方匹配：

```bash
python3 scripts/doctor.py match --text "你的报错"
```

如果你想修，先生成计划：

```bash
python3 scripts/doctor.py plan --text "你的问题"
```

看到计划后，再决定是否执行具体修改。
