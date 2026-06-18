# 皮皮虾医生药方库（OpenClaw Doctor Prescription Library）

Use exact matches first. If multiple prescriptions match, show the safest one first.

| ID | Symptoms | Plain diagnosis | Safe prescription | Risk |
|-|-|-|-|-|
| RX-HERMES-001 | `plugin.json`, `.hermes-skill`, `缺少 Hermes plugin`, `manifest missing` | Hermes 插件身份文件缺失，项目不能被正确识别。 | 补充 `.hermes-skill/plugin.json` 和基础字段；写入前展示文件内容。 | L1 |
| RX-HERMES-002 | `invalid json`, `JSONDecodeError`, `plugin.json 不是合法 JSON` | Hermes manifest 格式坏了，不是功能坏了。 | 用 JSON 解析定位错误行，最小修改修复格式。 | L1 |
| RX-HERMES-003 | `agents`, `缺少 agents`, `角色边界不清` | 诊断、修复、病历角色没有拆开，后续容易乱修。 | 补充 diagnosis/repair/case agent 文档。 | L1 |
| RX-HERMES-004 | `skills`, `缺少 skills`, `子 Skill`, `触发失败` | 子能力没有按命令拆分，Agent 不知道该用哪个能力。 | 补齐 `skills/<name>/SKILL.md` 并写清触发场景。 | L1 |
| RX-HERMES-005 | `scripts`, `CLI`, `本地执行入口`, `command not found` | 缺少可验证脚本或命令不可用，无法闭环测试。 | 补充本地 CLI；安装依赖前必须确认。 | L1/L2 |
| RX-HERMES-006 | `references`, `PRD`, `测试清单`, `安全策略` | 交付缺少 PRD、药方、安全策略或验收清单。 | 补齐 references，并让 README 写真实状态。 | L1 |
| RX-RUNTIME-001 | `fetch failed`, `Failed to fetch`, `访问不到`, `打开了但取不到`, `timeout`, `web data` | 网页数据获取链路失败，可能是网络、代理、平台限制或解析链路问题。 | 先区分访问不到和取不到；检查 timeout/代理/最小请求，不绕过登录、验证码、反爬或限流。 | L0/L2 |
| RX-RUNTIME-002 | `playwright`, `chromium`, `browser`, `screenshot`, `vision`, `截图失败` | 浏览器或视觉链路异常。 | 只读检查浏览器依赖和截图日志；安装浏览器依赖或重启前必须确认。 | L2 |
| RX-TOOL-001 | `unknown tool`, `tool not found`, `工具不存在`, `工具调用失败` | Agent 调用了未注册、未暴露或名称不一致的工具。 | 对照工具注册表和调用名；修配置或代码前展示目标文件和最小 diff。 | L1/L2 |
| RX-DEP-001 | `ModuleNotFoundError`, `No module named`, `找不到模块`, `找不到依赖` | Python 依赖缺失或解释器环境不对。 | 确认解释器和项目环境；安装前展示命令并确认。 | L2 |
| RX-FILE-001 | `No such file`, `ENOENT`, `path not found`, `找不到文件`, `找不到路径` | 命令找不到目标路径。 | 先确认当前目录和绝对路径；创建目录前必须确认。 | L0/L1 |
| RX-AUTH-001 | `401`, `unauthorized`, `invalid token`, `missing_scope`, `鉴权失败`, `token过期` | 登录态、授权或 scope 不可用。 | 重新授权或补最小权限；不要打印 token。 | L2 |
| RX-SAFETY-001 | `cookie`, `token`, `password`, `private key`, `私钥`, `密码`, `API Key` | 输入或日志里可能包含敏感信息。 | 立即脱敏；不要写入病历或群聊回显。 | L3 |
| RX-SAFETY-002 | `login required`, `captcha`, `rate limit`, `too many requests`, `登录`, `验证码`, `请求太频繁` | 平台要求登录、验证码或触发限流，不能当作普通程序错误硬修。 | 停止自动重试；提示合规登录或降低频率，不收集 cookie/token，不绕过平台保护。 | L3 |
| RX-REPAIR-001 | `帮我修`, `自愈`, `怎么修`, `需要修复计划` | 用户需要安全修复步骤，而不是立即执行。 | 生成修复计划，包含影响范围、确认要求、验证和回滚。 | L0 |
| RX-REPAIR-002 | `删除`, `覆盖`, `reset --hard`, `rm -rf`, `危险操作` | 请求包含破坏性动作。 | 升级 L3，只给人工计划，必须明确批准精确动作。 | L3 |
| RX-CASE-001 | `上次`, `病历`, `历史`, `怎么处理`, `查病历` | 用户在查历史处理记录。 | 调用 case search 返回最近匹配记录。 | L0 |
| RX-FEISHU-001 | `凡宇科技医生 体检`, `看看状态`, `体检` | 飞书消息可路由到只读体检。 | 使用 route 判断意图，再调用 check。 | L0 |
| RX-FEISHU-002 | `凡宇科技医生 报错了`, `出错了`, `报错` | 飞书消息可路由到药方匹配。 | 提取冒号后的错误正文，调用 match。 | L0 |
| RX-FEISHU-003 | `凡宇科技医生 帮我修一下`, `自愈`, `帮我修` | 飞书消息涉及修复，不能直接执行。 | 调用 plan 生成计划，等待用户确认。 | L2 |
| RX-OPENCLAW-001 | `SOUL.md`, `AGENTS.md`, `缺少核心文件`, `缺少 IDENTITY` | OpenClaw 核心文件缺失，启动可能不完整。 | 补充缺失的核心文件。 | L1 |
| RX-OPENCLAW-002 | `cron`, `定时任务`, `cron_tasks.json`, `cron 异常` | OpenClaw 定时任务配置可能有问题。 | 检查最近 cron 运行日志和配置文件。 | L2 |
| RX-OPENCLAW-003 | `HEARTBEAT`, `心跳`, `HEARTBEAT.md` | 心跳巡检异常或 HEARTBEAT.md 格式异常。 | 检查心跳 cron 配置和 gateway 状态，修复 HEARTBEAT.md 格式。 | L2 |
| RX-OPENCLAW-004 | `band`, `bandrouter`, `乐队协作`, `乐队`, `路由失败` | 乐队协作路由组件异常。 | 检查 band 目录和配置文件。 | L2 |
| RX-MEM-001 | `MEMORY.md`, `memory/`, `记忆`, `记忆过大`, `记忆膨胀` | 记忆系统文件过大或文件过多，影响加载性能。 | 蒸馏精简 MEMORY.md，归档旧记忆文件。 | L1 |
| RX-MEM-002 | `hearbeats`, `heartbeat/`, `心跳记录过多` | memory/heartbeat/ 目录文件数超过阈值。 | 清理超过30天的历史心跳记录。 | L1 |
| RX-SKILL-001 | `SKILL.md`, `缺少 Skill`, `Skill 结构不完整`, `Codex 无法识别` | Skill 包结构不完整，缺少入口文件。 | 补充 SKILL.md 及必要子目录。 | L1 |
| RX-SKILL-002 | `agents/openai.yaml`, `缺少 openai.yaml`, `UI 触发配置缺失` | Skill 缺少 UI 触发配置，无法被界面识别。 | 补充 agents/openai.yaml，default_prompt 包含 skill-name。 | L1 |
| RX-SKILL-003 | `__pycache__`, `临时文件`, `缓存文件`, `pyc` | 项目包含不必要的缓存文件。 | 清理 `__pycache__` 和 `.pyc` 文件。 | L0 |
| RX-SKILL-004 | `description`, `触发词`, `可触发`, `Skill 描述过短` | Skill 的 description 不够详细，Agent 不清晰何时触发。 | 补充能力描述、触发词和适用场景。 | L1 |
| RX-SYS-001 | `load average`, `负载高`, `CPU 高`, `系统资源不足` | 系统负载偏高，可能影响响应速度。 | 检查后台进程，关闭不必要的应用。 | L2 |
| RX-SYS-002 | `磁盘`, `disk`, `磁盘空间`, `磁盘不足` | 磁盘使用率偏高。 | 清理不需要的文件，特别关注 logs 和临时文件。 | L1 |
| RX-LOG-001 | `error`, `failed`, `exception`, `日志错误` | 最近日志包含错误信息。 | 查看日志详情，确定根因。 | L0 |
| RX-LOG-002 | `日志过大`, `日志膨胀`, `日志文件过多` | 日志文件过多或过大。 | 启用日志轮转，归档旧日志。 | L1 |
| RX-FILE-003 | `Git 未提交`, `working tree`, `未提交改动`, `dirty` | Git 工作区有未提交改动，修改时需保护。 | 修改前查看相关 diff，只处理本任务文件。 | L0 |
| RX-FILE-004 | `备份`, `backup`, `恢复`, `回滚` | 需要备份或回滚文件。 | 修改前先备份，使用 cp file file.backup.$(date +%s)。 | L0 |
