#!/usr/bin/env python3
"""OpenClaw Doctor v5.0 — 锋式十步法（PRIMARY TROUBLESHOOTING METHOD）

Implements PRD 4.2.7 「诊断逻辑（十步法）」，引用用户 SOUL/AGENTS 里固化的
「剥离情绪 → 定真问题 → 判类型 → 圈边界 → 拆细碎 → 找根因 → 选方案 → 控风险 → 明权责 → 常固化」方法论。

设计参照: 医学鉴别诊断的排除法 (PRD 4.2.7)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal


# ---------------------------------------------------------------------------
# 十步法 (per 用户 SOUL/AGENTS 「十步法问题排查口诀」)
# ---------------------------------------------------------------------------
TEN_STEPS: list[dict] = [
    {
        "step": 1,
        "name": "剥离情绪",
        "core": "停主观吐槽，记录时间/场景/现象/影响/数据",
        "output": "客观事件陈述",
    },
    {
        "step": 2,
        "name": "定真问题",
        "core": "问三遍：现状？理想？差距？避免把症状当问题",
        "output": "一句话真问题",
    },
    {
        "step": 3,
        "name": "判类型",
        "core": "突发救火 / 结构优化 / 决策选择 / 协同沟通",
        "output": "类型+优先级",
    },
    {
        "step": 4,
        "name": "圈边界",
        "core": "拆可控项+不可控项，聚焦可控",
        "output": "可执行清单",
    },
    {
        "step": 5,
        "name": "拆细碎",
        "core": "MECE 拆 3-5 个独立子问题",
        "output": "子问题列表",
    },
    {
        "step": 6,
        "name": "找根因",
        "core": "三连问：为什么会发生？为什么没提前发现？为什么会重复出现？",
        "output": "根因+三连问",
    },
    {
        "step": 7,
        "name": "选方案",
        "core": "先发散再收敛，按「低成本/快见效/低风险/易落地」筛",
        "output": "最优方案",
    },
    {
        "step": 8,
        "name": "控风险",
        "core": "预判漏洞/卡点/失败后果，提前制定兜底预案",
        "output": "风险清单+回滚",
    },
    {
        "step": 9,
        "name": "明权责",
        "core": "谁牵头/谁配合/交付标准/截止时间，同步对齐",
        "output": "责任矩阵",
    },
    {
        "step": 10,
        "name": "常固化",
        "core": "沉淀 SOP/规则/模板，避免同类问题重复",
        "output": "标准化产出",
    },
]


# 问题类型 (per SOUL 「问题类型·处理原则」)
PROBLEM_TYPES: dict[str, dict] = {
    "突发救火": {
        "signal": "报错/服务挂/安全告警/数据异常",
        "priority": "🔴 最高",
        "principle": "先止损再溯源，10 分钟内出第一响应",
    },
    "结构优化": {
        "signal": "长期方案/架构升级/债务清理",
        "priority": "🟡 中",
        "principle": "完整 12 阶段，长期价值优先",
    },
    "决策选择": {
        "signal": "要不要/做不做/选哪个",
        "priority": "🟢 较低",
        "principle": "出对比方案+利弊+风险，等用户确认",
    },
    "协同沟通": {
        "signal": "跨角色/对齐目标/争议澄清",
        "priority": "🟢 较低",
        "principle": "先共识后执行，记录决策依据",
    },
}


@dataclass
class CaseState:
    """十步法会话状态。"""

    case_id: str
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    subjective: str = ""  # Step 1
    real_problem: str = ""  # Step 2
    problem_type: str = ""  # Step 3
    controllable: list[str] = field(default_factory=list)  # Step 4
    sub_problems: list[str] = field(default_factory=list)  # Step 5
    root_causes: list[str] = field(default_factory=list)  # Step 6
    chosen_solution: str = ""  # Step 7
    risks: list[str] = field(default_factory=list)  # Step 8
    ownership: dict = field(default_factory=dict)  # Step 9
    deliverables: list[str] = field(default_factory=list)  # Step 10
    completed: bool = False

    def progress(self) -> int:
        """计算完成度（10 步各 10%）。"""
        fields = [
            self.subjective, self.real_problem, self.problem_type, self.controllable,
            self.sub_problems, self.root_causes, self.chosen_solution, self.risks,
            self.ownership, self.deliverables,
        ]
        filled = sum(1 for f in fields if f and (not isinstance(f, list) or len(f) > 0))
        return filled * 10


def render_wizard(case: CaseState, current_step: int) -> str:
    """渲染当前步骤的引导话术。"""
    step = TEN_STEPS[current_step - 1]
    lines = [
        f"🦐 皮皮虾医生 锋式十步法 · 第 {current_step}/10 步",
        "",
        f"## {step['step']}. {step['name']}",
        "",
        f"**核心动作**：{step['core']}",
        f"**输出**：{step['output']}",
    ]

    if current_step == 1:
        if not case.subjective:
            lines.append("")
            lines.append("请描述：**什么时候、什么场景、发生了什么、影响范围、有哪些数据**。")
            lines.append("避免使用「烦死了」「太坑了」等情绪化表达。")
        else:
            lines.append(f"\n✅ 已记录客观事件：{case.subjective[:100]}...")

    elif current_step == 3:
        lines.append("")
        lines.append("可选问题类型：")
        for ptype, info in PROBLEM_TYPES.items():
            lines.append(f"  **{ptype}**（{info['priority']}）：{info['signal']} → {info['principle']}")

    elif current_step == 6:
        lines.append("")
        lines.append("三连问：")
        lines.append("  1. **为什么会发生？**（直接原因）")
        lines.append("  2. **为什么没提前发现？**（检测盲点）")
        lines.append("  3. **为什么会重复出现？**（机制缺失）")

    elif current_step == 8:
        lines.append("")
        lines.append("风险等级：L0 只读 | L1 低风险写 | L2 中风险 | L3 高风险（不可自动）")

    elif current_step == 10:
        lines.append("")
        lines.append("固化形式：")
        lines.append("  - 写入 evolution_gate/learning_log.md")
        lines.append("  - 更新 references/prescriptions.md（新增药方）")
        lines.append("  - 更新 references/safety_policy.md（如涉及安全）")

    return "\n".join(lines)


def render_summary(case: CaseState) -> str:
    """渲染完整总结。"""
    lines = [
        "🦐 皮皮虾医生 锋式十步法 · 完整诊断",
        "",
        f"案例 ID：{case.case_id}",
        f"开始：{case.started_at}",
        f"完成度：{case.progress()}%",
        "",
    ]
    for i, step in enumerate(TEN_STEPS, 1):
        lines.append(f"## {step['step']}. {step['name']}")
        value = getattr(case, [
            "subjective", "real_problem", "problem_type", "controllable",
            "sub_problems", "root_causes", "chosen_solution", "risks",
            "ownership", "deliverables"
        ][i - 1])
        if isinstance(value, list):
            if value:
                for v in value:
                    lines.append(f"  - {v}")
            else:
                lines.append("  - （未填写）")
        elif isinstance(value, dict):
            if value:
                for k, v in value.items():
                    lines.append(f"  - {k}: {v}")
            else:
                lines.append("  - （未填写）")
        else:
            lines.append(f"  {value or '（未填写）'}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenClaw Doctor 锋式十步法")
    parser.add_argument("--mode", choices=["wizard", "summary", "demo"], default="wizard")
    parser.add_argument("--state-file", default="state/ten_step_state.json")
    parser.add_argument("--step", type=int, default=1, help="wizard 当前步骤 (1-10)")
    parser.add_argument("--case-id", default="default", help="案例 ID")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    if args.mode == "demo":
        # 跑一个完整的 demo case
        case = CaseState(
            case_id="demo-2026-06-08",
            subjective="示例: Agent 静默时无 watchdog，sub-agent 失联导致任务半完成",
            real_problem="示例: Agent 静默时无 watchdog，sub-agent 失联导致任务半完成",
            problem_type="突发救火",
            controllable=[
                "加 sub-agent watchdog（cron 监测 + 自动重启）",
                "AGENTS.md 定时报告章节加硬约束",
            ],
            sub_problems=[
                "为什么 main session 会失约？",
                "为什么补救推送是 info 而非晨报？",
                "为什么静默规则没生效？",
            ],
            root_causes=[
                "没有 watchdog 监测 main session 活跃度",
                "AGENTS.md 章节给 main 自由发挥空间",
                "HEARTBEAT 静默规则只针对 info 推送，没约束补救推送",
            ],
            chosen_solution="方案 B：合并版 PRD + L0 PCEC 自愈 + HEARTBEAT 新通道（用户决策 2026-06-08）",
            risks=[
                "L0 自动执行可能误操作（白名单约束）",
                "新 HEARTBEAT 通道可能刷屏（推送分级）",
            ],
            ownership={"owner": "守夜人", "reviewer": "用户", "deadline": "Week 4"},
            deliverables=[
                "v5.0 PRD 合并版",
                "heartbeat.py + pcec_engine.py",
                "findings.md + progress.md",
            ],
            completed=True,
        )
        if args.format == "json":
            print(json.dumps(asdict(case), ensure_ascii=False, indent=2))
        else:
            print(render_summary(case))
        return 0

    # wizard / summary 模式
    state_path = Path(args.state_file)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    if state_path.exists():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            case = CaseState(**{k: v for k, v in data.items() if k in CaseState.__annotations__})
        except Exception:
            case = CaseState(case_id=args.case_id)
    else:
        case = CaseState(case_id=args.case_id)

    if args.mode == "summary":
        print(render_summary(case))
    else:
        print(render_wizard(case, args.step))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
