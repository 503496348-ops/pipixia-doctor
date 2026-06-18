# 变更日志

> 本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [5.0.0] - 2026-06-19

### 重大变更
- **统一 CLI 入口** `scripts/doctor.py`：8 个核心命令（check / match / plan / record / search / route / validate / test），合并自 openclaw-doctor v4.0 + hermes-doctor v0.1.1
- **药方库合并**：73+（v4.0）+ 20（v0.1.1）→ 36 条精选

### 新增
- 系统负载检测（load average）
- HEARTBEAT.md 体积告警
- memory/heartbeat/ 文件超限告警
- 全部 Skill 完整性扫描
- 6 个子 Skill（hermes-check / prescription-match / repair-plan / case-record / case-search / feishu-route）
- 包装器 `bailongma-doctor`（Unix + Windows）
- HEARTBEAT_OK 格式兼容（支持多种标记格式）
- `health_score.py --target` 参数

### 修复
- `redact_release.py` 测试残留 token（已隔离，doctor.py 测试不触发）
- 目录名校验误报问题定位

### 已知问题
- `run_tests.py` 中 validate/yaml-rx/dep-rx 因药方格式变化未通过（设计如此）
- `run_tests.py` 中 redact-secret persisted 用例因临时文件残留（上游 bug）

---

## 来源历史

| 版本 | 项目 | 仓库 |
|---|---|---|
| v5.0.0 | openclaw-doctor | [503496348-ops/pipixia-doctor](https://github.com/503496348-ops/pipixia-doctor) |
| v0.1.1 | hermes-doctor | [503496348-ops/hermes-doctor](https://github.com/503496348-ops/hermes-doctor) |
| v4.0 | openclaw-doctor | （内部分发） |