# 皮皮虾医生v5.1

> 版本: 5.1.0 | 品牌: AtomCollide-智械工坊
> 发布日期: 2026-06-20

## 快速开始

```bash
# 统一入口
python3 scripts/doctor.py check --target . --format markdown
python3 scripts/doctor.py test --target .

# 旧入口（向后兼容）
python3 scripts/doctor_check.py --target . --format markdown
```

## v5.1 新增：数字遗产 + 智能进化

### 🗂️ Agent 快照与恢复（数字遗产+复活）

完整捕获 Agent 状态（SOUL/MEMORY/skills/configs），支持版本化快照、差异对比和一键恢复。

```bash
# 创建快照
python3 scripts/doctor.py snapshot --target . --snapshot-action save --description "修复前备份"

# 列出所有快照
python3 scripts/doctor.py snapshot --target . --snapshot-action list

# 对比两个快照
python3 scripts/doctor.py snapshot --target . --snapshot-action diff --snapshot-id snap-A --other-snapshot-id snap-B

# 验证当前状态与快照是否一致
python3 scripts/doctor.py snapshot --target . --snapshot-action verify --snapshot-id snap-XXXX

# 从快照恢复（预演模式）
python3 scripts/doctor.py snapshot --target . --snapshot-action restore --snapshot-id snap-XXXX --dry-run

# 独立脚本
python3 scripts/agent_snapshot.py --target . --mode save --description "备份描述"
```

**核心能力：**
- 快照 = tar.gz 归档 + SHA-256 校验清单
- 自动收集 SOUL.md、MEMORY.md、skills/、memory/、cron/ 等关键文件
- 恢复前自动创建备份（安全回滚）
- 支持 dry-run 预演模式

### 🧠 药方自学习引擎（智能进化）

反馈驱动的药方优化：追踪药方命中率、分析未覆盖错误模式、自动生成候选药方。

```bash
# 完整学习报告
python3 scripts/doctor.py learn --target . --learn-action report

# 记录反馈（药方命中/未命中/有效/无效）
python3 scripts/doctor.py learn --target . --learn-action feedback \
  --rx-id RX-AUTH-001 --query "missing_scope error" --outcome hit --resolved

# 药方效果分析
python3 scripts/doctor.py learn --target . --learn-action effectiveness

# 生成候选药方（从未解决的重复错误中学习）
python3 scripts/doctor.py learn --target . --learn-action candidates

# 药方覆盖率缺口分析
python3 scripts/doctor.py learn --target . --learn-action gaps

# 独立脚本
python3 scripts/rx_learner.py --target . --mode report
```

**核心能力：**
- 追踪每个药方的命中/未命中/有效/无效反馈
- 计算成功率和趋势（improving/declining/stable）
- 从未解决的重复错误中自动聚类生成候选药方
- 从用户手动解决的案例中提取新药方建议

## v5.0 增量改进

| 改进 | 来源 |
|------|------|
| 统一 CLI (`doctor.py`): check/match/plan/record/search/route/validate/test/snapshot/learn | hermes-doctor + v5.1 |
| Agent 深度检查: 系统负载/HEARTBEAT体积/memory/heartbeat文件数/Skill完整性 | 审计发现 |
| 系统资源检测: load average, 磁盘提示 | 审计发现 |
| 药方库合并: 90+ 药方 | 双源合并 |
| 包装器: bailongma-doctor (Unix + Windows) | hermes-doctor |
| Hermes插件兼容: .hermes-skill/plugin.json | 兼容层 |
| 子Skills: 6个 | hermes-doctor |

## CLI 命令总览

| 命令 | 说明 | 风险等级 |
|------|------|---------|
| `check` | 只读健康检查 | L0 |
| `match` | 药方匹配 | L0 |
| `plan` | 修复计划生成 | L2 |
| `record` | 脱敏病历写入 | L1 |
| `search` | 病历搜索 | L0 |
| `route` | 飞书消息路由 | L0 |
| `validate` | 包结构验证 | L0 |
| `test` | 集成测试 (11项) | L0 |
| `snapshot` | Agent快照与恢复 | L0-L3 |
| `learn` | 药方自学习 | L0 |

## 目录结构

见 SKILL.md。

## 竞品对标

| 能力 | 皮皮虾医生 v5.1 | 通用工作流平台 | 通用链路框架 | 通用多代理框架 |
|------|-----------------|------|-----------|---------|
| Agent健康诊断 | ✅ 深度体检+药方库 | ❌ | ❌ | ❌ |
| 自愈引擎 | ✅ PCEC循环 | ❌ | ❌ | ❌ |
| 数字遗产 | ✅ 快照+恢复 | ⚠️ 版本管理 | ⚠️ 序列化 | ❌ |
| 智能进化 | ✅ 药方自学习 | ⚠️ 标注反馈 | ❌ | ⚠️ 学习循环 |
| 多Agent协同 | ❌ (v6.2规划) | ✅ | ✅ | ✅ |
| 工作流编排 | ❌ | ✅ | ✅ | ✅ |

---



---

## 🚀 加入AtomCollide-AI智能体实验室

**元素碰撞-AtomCollide-AI 智能体实验室** 是一个专注于AI领域的开源组织，汇聚了众多优秀学习者。

### 核心价值

**找工作：更省力，也更精准**
- 一线大厂内推通道（字节、阿里、腾讯等）
- 全链路求职赋能包（面试题库、简历优化、晋升指导）
- 线下技术沙龙 & 人脉网络

**学AI测试：真正落地，拒绝空谈**
- 从0到1实战落地体系（Skills、MCP、RAG、AI IDE等）
- 独家自研资料与工具矩阵
- 前沿技术同步与提效方案

### 知识库

- [踩坑合集](https://vcnvmnln7wit.feishu.cn/wiki/CjV9wG8IHiIpWikCdFEcxfErnne)
- [商业化案例库](https://vcnvmnln7wit.feishu.cn/wiki/LdIxwlrKGibFEVkWMocc2K9KnBh)
- [科普专栏](https://vcnvmnln7wit.feishu.cn/wiki/K1RPwM8zji9ZchkxlOmcivUgnJe)
- [Open Build](https://vcnvmnln7wit.feishu.cn/wiki/CThswol0PiNJJbkhgT1cZIxanLb)
- [LLM/Agent/研究报告知识库](https://vcnvmnln7wit.feishu.cn/wiki/KwGQwS2TciT2EdkSBBtcYnbsnSd)
- [Skill封装合集](https://vcnvmnln7wit.feishu.cn/wiki/PDfpwqJZUibTyBkUa7TcZZ6Onpd)
- [社区治理运营知识库](https://vcnvmnln7wit.feishu.cn/wiki/MSEGwrdnTiiF9Dk8qCVcNW6InJg)

### 加入社群

| 社群 | 链接 |
|------|------|
| AI探索交流1区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=074vd565-6084-455c-ac52-9703e89a0697) |
| AI探索交流2区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=60bj94f0-1a67-48a7-abbb-9172b161c2b0) |
| AI探索交流3区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=13do1920-db46-4444-b635-005680beaf58) |
| AI探索交流4区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=f17o1b86-06f6-4f10-911a-69a299a25fe3) |
| AI探索交流5区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=2bbh6ab6-22c2-4753-b973-74bb1a2edcc9) |
| AI探索交流6区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=d19r19f7-2f47-42ba-b1ec-cb0342cf2e80) |
| AI探索交流7区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=fe9vdacc-7316-4b4d-ae4a-fdbcf56315e6) |
| AI探索交流8区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=103kfae8-1fd7-424f-984f-d66c210e42d1) |
| AI探索交流9区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=239p3cad-2f83-4baa-a230-f40386067548) |
| AI探索交流10区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=880r7cf5-3638-45ff-afb9-7944de991872) |
| AI探索交流-网文作家 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=6a3v579b-ab43-4e1a-87f9-be63bab88da7) |
| AI探索交流群-音乐达人 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=76at299e-73da-4eeb-9eba-32161e98f2f8) |
| AI探索交流群-微笑驿站 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=f2av73d0-6bb4-4a9f-9095-5fbbe83e49ec) |

---

*AtomCollide-智械工坊团队出品*

---

## 组织与社群入口

**元素碰撞 · AtomCollide-AI 智能体实验室**：面向学习者、创作者与自动化实践者，持续沉淀可复用的 AI Agent 产品、工作流与工程经验。使命：**for the learner**。

> 请选择 1 个常用社群加入，内容全域同步，无需重复加入。

### 知识库

| 知识库 | 链接 |
|---|---|
| 踩坑合集 | [进入](https://vcnvmnln7wit.feishu.cn/wiki/CjV9wG8IHiIpWikCdFEcxfErnne) |
| 商业化案例库 | [进入](https://vcnvmnln7wit.feishu.cn/wiki/LdIxwlrKGibFEVkWMocc2K9KnBh) |
| 科普专栏 | [进入](https://vcnvmnln7wit.feishu.cn/wiki/K1RPwM8zji9ZchkxlOmcivUgnJe) |
| Open Build | [进入](https://vcnvmnln7wit.feishu.cn/wiki/CThswol0PiNJJbkhgT1cZIxanLb) |
| LLM / Agent / 研究报告 | [进入](https://vcnvmnln7wit.feishu.cn/wiki/KwGQwS2TciT2EdkSBBtcYnbsnSd) |
| Skill 封装合集 | [进入](https://vcnvmnln7wit.feishu.cn/wiki/PDfpwqJZUibTyBkUa7TcZZ6Onpd) |
| 社区治理运营 | [进入](https://vcnvmnln7wit.feishu.cn/wiki/MSEGwrdnTiiF9Dk8qCVcNW6InJg) |

### 社群邀请

| 社群 | 链接 |
|---|---|
| AI 探索交流 1 区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=074vd565-6084-455c-ac52-9703e89a0697) |
| AI 探索交流 2 区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=60bj94f0-1a67-48a7-abbb-9172b161c2b0) |
| AI 探索交流 3 区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=13do1920-db46-4444-b635-005680beaf58) |
| AI 探索交流 4 区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=f17o1b86-06f6-4f10-911a-69a299a25fe3) |
| AI 探索交流 5 区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=2bbh6ab6-22c2-4753-b973-74bb1a2edcc9) |
| AI 探索交流 6 区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=d19r19f7-2f47-42ba-b1ec-cb0342cf2e80) |
| AI 探索交流 7 区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=fe9vdacc-7316-4b4d-ae4a-fdbcf56315e6) |
| AI 探索交流 8 区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=103kfae8-1fd7-424f-984f-d66c210e42d1) |
| AI 探索交流 9 区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=239p3cad-2f83-4baa-a230-f40386067548) |
| AI 探索交流 10 区 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=880r7cf5-3638-45ff-afb9-7944de991872) |
| AI 探索交流 — 网文作家 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=6a3v579b-ab43-4e1a-87f9-be63bab88da7) |
| AI 探索交流群 — 音乐达人 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=76at299e-73da-4eeb-9eba-32161e98f2f8) |
| AI 探索交流群 — 微笑驿站 | [加入](https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=f2av73d0-6bb4-4a9f-9095-5fbbe83e49ec) |

---

AtomCollide-智械工坊团队出品。更多产品见：[AtomCollide Product Matrix](https://503496348-ops.github.io/atomcollide-product-matrix/)。


## 示例输出

本仓库的最小可验证使用路径：

1. 阅读 README 的 Quick Start / 使用说明，完成本地安装或配置。
2. 按仓库提供的命令、脚本或入口运行一次最小任务。
3. 对照本产品定位验证输出：**皮皮虾医生（PipiXia Doctor）** 属于 **智能体健康** 产品，目标是把输入材料转化为可检查、可复用的结果。
4. 若运行环境暂不可用，先通过 README、CHANGELOG、CI 状态和源码结构完成静态验收，再补充真实截图或录屏。

> 维护要求：后续每次发布都应把真实运行截图、CLI 输出、网页截图或 API 响应样例补充到本节，避免仓库首页只描述能力、不展示结果。

## Governance Links

- [LICENSE](LICENSE)
- [CHANGELOG](CHANGELOG.md)
- [SECURITY](SECURITY.md)
- [CONTRIBUTING](CONTRIBUTING.md)



## 2026-07-03 运行时增强

- 新增检索过滤注入探针，拦截未知过滤键、空值和危险过滤片段。
- 交付物包含可导入模块与定向单元测试。

## 2026-07-03 产品收敛门禁

- 新增 `scripts/product_convergence_gate.py`：从远端干净 clone 后可运行 `python3 scripts/product_convergence_gate.py --json`，检查 SKILL/README、入口文件、smoke 目标、测试与外部融合引用是否自洽。
- 新增 `tests/test_product_convergence_gate.py`：确保门禁在产品仓库中真实可执行，避免后续增强只停留在孤岛模块。
