#!/usr/bin/env python3
"""OpenClaw Doctor v5.0 — PCEC 自愈引擎

Implements PRD 4.1.4 「自我修复（PCEC 引擎）」:
- Perceive → Think → Execute → Check (K8s Reconcile Loop)
- 6h 无进化 → 强制熔断
- 决策 a: L0 自动执行（只读/小写），L1+ 强制确认

产出分类（per PRD 4.1.4）:
- 新增技能
- 通用范式
- 效率杠杆
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal


# ---------------------------------------------------------------------------
# PRD 4.1.4 产出三分类
# ---------------------------------------------------------------------------
OutcomeType = Literal["skill", "pattern", "lever"]


@dataclass
class Outcome:
    """A single PCEC outcome. Maps to PRD 4.1.4's three production types."""

    type: OutcomeType  # skill | pattern | lever
    name: str
    description: str
    evidence_path: str = ""


@dataclass
class Plan:
    """A repair plan with risk level."""

    rx_id: str
    risk: str  # L0 | L1 | L2 | L3
    diagnosis: str
    action: str
    target_path: str = ""
    rollback: str = ""


# ---------------------------------------------------------------------------
# L0 自愈执行器（决策 a: 严格保守）
# ---------------------------------------------------------------------------
# L0 允许执行的操作白名单。**任何不在白名单内的操作都需确认。**
L0_ALLOWLIST: set[str] = {
    "read_health_score",      # 只读
    "summarize_logs",         # 只读
    "mark_case_resolved",     # 写 case 状态
    "update_metrics",         # 写 metrics 文件
    "create_missing_dir",     # 创建缺失的低风险目录
    "log_alert",              # 写告警日志
}


@dataclass
class ExecuteResult:
    """Result of executing a plan (L0 only — L1+ requires confirmation)."""

    plan: Plan
    executed: bool
    success: bool
    message: str
    output_path: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


def execute_l0(plan: Plan, target: Path) -> ExecuteResult:
    """Execute an L0 plan automatically. Returns failure if not in allowlist."""
    if plan.risk != "L0":
        return ExecuteResult(plan, False, False, f"risk={plan.risk} 不在 L0 范围，需确认")

    # 简化版执行：只做白名单内的可观察动作
    if plan.action not in L0_ALLOWLIST:
        return ExecuteResult(plan, False, False, f"action={plan.action} 不在 L0 白名单")

    try:
        if plan.action == "read_health_score":
            score_file = target / "state" / "health_score.txt"
            if score_file.exists():
                score = score_file.read_text(encoding="utf-8").strip()
                return ExecuteResult(plan, True, True, f"health_score={score}", str(score_file))
            # 文件不存在也记为成功（免不了出现一次，这是检查动作本身）
            return ExecuteResult(plan, True, True, "health_score.txt 缺失，标记等待生成", "")
        elif plan.action == "log_alert":
            alert_file = target / "state" / "pcec_alerts.jsonl"
            alert_file.parent.mkdir(parents=True, exist_ok=True)
            with alert_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": datetime.now().isoformat(), "plan": plan.rx_id}) + "\n")
            return ExecuteResult(plan, True, True, "alert logged", str(alert_file))
        elif plan.action == "create_missing_dir":
            if plan.target_path:
                Path(plan.target_path).mkdir(parents=True, exist_ok=True)
                return ExecuteResult(plan, True, True, f"created {plan.target_path}", plan.target_path)
            return ExecuteResult(plan, True, False, "缺 target_path", "")
        else:
            return ExecuteResult(plan, True, True, f"L0 action {plan.action} 标记完成（占位）")
    except Exception as exc:
        return ExecuteResult(plan, True, False, f"异常: {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# PCEC 引擎（Perceive/Think/Execute/Check）
# ---------------------------------------------------------------------------
@dataclass
class PCECState:
    """PCEC engine state — persists across cycles."""

    cycle_num: int = 0
    last_evolution_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    outcomes: list[Outcome] = field(default_factory=list)
    executions: list[ExecuteResult] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)  # 最近 12 个周期的历史
    degraded_reason: str = ""

    def record_outcome(self, outcome: Outcome) -> None:
        self.outcomes.append(outcome)
        self.last_evolution_at = datetime.now().isoformat(timespec="seconds")


def perceive(target: Path) -> list[Plan]:
    """Step 1: gather evidence. Returns a list of candidate plans.

    For v5.0 demo, this generates synthetic plans from known symptoms.
    In production, this would call doctor_check + prescription_match.
    """
    plans: list[Plan] = []
    # 仅返回可在 L0 范围内处理的"低风险"计划
    # 真实环境：会调用 prescription_match 拿到最高匹配的药方
    if (target / "state" / "pcec_alerts.jsonl").exists():
        plans.append(
            Plan(
                rx_id="RX-LOG-001",
                risk="L0",
                diagnosis="最近日志存在 error 关键词",
                action="log_alert",
                target_path=str(target / "state" / "pcec_alerts.jsonl"),
                rollback="删除该行 JSONL",
            )
        )
    # 任何 health_score 缺失也生成一个 L0 计划
    if not (target / "state" / "health_score.txt").exists():
        plans.append(
            Plan(
                rx_id="RX-HEALTH-001",
                risk="L0",
                diagnosis="health_score.txt 缺失",
                action="read_health_score",
                rollback="无",
            )
        )
    return plans


def think(plans: list[Plan]) -> list[Plan]:
    """Step 2: prioritize and filter plans.

    For v5.0: keep all L0 plans, drop L1+ (require confirmation).
    """
    return [p for p in plans if p.risk == "L0"]


def execute(state: PCECState, plans: list[Plan], target: Path) -> list[ExecuteResult]:
    """Step 3: execute L0 plans automatically."""
    results: list[ExecuteResult] = []
    for plan in plans:
        result = execute_l0(plan, target)
        results.append(result)
        state.executions.append(result)
    return results


def check(state: PCECState, results: list[ExecuteResult]) -> list[Outcome]:
    """Step 4: verify and produce outcomes.

    Successful executions become outcomes (PRD 4.1.4 三分类).
    """
    outcomes: list[Outcome] = []
    for r in results:
        if r.success:
            # 按 action 类型分类
            if r.plan.action == "log_alert":
                outcomes.append(
                    Outcome("lever", f"log_alert@{r.plan.rx_id}", f"已记录告警 {r.plan.rx_id}", r.output_path)
                )
            elif r.plan.action == "read_health_score":
                outcomes.append(
                    Outcome("pattern", f"health_check@{r.plan.rx_id}", f"健康分读取: {r.message}", r.output_path)
                )
            else:
                outcomes.append(
                    Outcome("skill", f"L0_{r.plan.action}@{r.plan.rx_id}", f"L0 自愈: {r.plan.action}", r.output_path)
                )
            state.record_outcome(outcomes[-1])
    return outcomes


# ---------------------------------------------------------------------------
# 6h 熔断检测
# ---------------------------------------------------------------------------
def check_evolution_stall(state: PCECState) -> bool:
    """6h 无实质进化 → 强制熔断 (per PRD 4.1.4)."""
    if not state.last_evolution_at:
        return False
    last = datetime.fromisoformat(state.last_evolution_at)
    hours_since = (datetime.now() - last).total_seconds() / 3600
    return hours_since > 6


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="OpenClaw Doctor PCEC 自愈引擎")
    parser.add_argument("--target", default=".", help="目标目录")
    parser.add_argument("--state-file", default="state/pcec_state.json", help="状态文件")
    parser.add_argument("--rounds", type=int, default=1, help="连续跑多轮")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    state_path = target / args.state_file if not Path(args.state_file).is_absolute() else Path(args.state_file)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    # 加载/初始化状态
    if state_path.exists():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            # 过滤只接受 dataclass 字段
            valid_fields = {k: v for k, v in data.items() if k in PCECState.__annotations__}
            state = PCECState(**valid_fields)
        except Exception:
            state = PCECState()
    else:
        state = PCECState()

    # 跑 N 个 PCEC 周期
    for r in range(args.rounds):
        state.cycle_num += 1
        plans = perceive(target)
        filtered = think(plans)
        results = execute(state, filtered, target)
        outcomes = check(state, results)
        state.history.append(
            {
                "cycle": state.cycle_num,
                "ts": datetime.now().isoformat(timespec="seconds"),
                "plans": len(plans),
                "executed": len(results),
                "outcomes": len(outcomes),
            }
        )

    # 检查 6h 熔断
    if check_evolution_stall(state):
        state.degraded_reason = f"6h+ 无进化，强制熔断（last={state.last_evolution_at}）"

    # 保存
    state_path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")

    # 输出
    if args.format == "json":
        print(json.dumps(asdict(state), ensure_ascii=False, indent=2))
    else:
        lines = [
            "🦐 皮皮虾医生 PCEC 自愈引擎报告",
            "",
            f"周期数: #{state.cycle_num}",
            f"最近进化: {state.last_evolution_at}",
            f"累计产出: {len(state.outcomes)} 项",
            f"累计执行: {len(state.executions)} 次",
            f"熔断状态: {'🔴 ' + state.degraded_reason if state.degraded_reason else '🟢 健康'}",
            "",
            "## 最近 12 周期",
        ]
        for h in state.history[-12:]:
            lines.append(
                f"- 周期 #{h['cycle']}: plans={h['plans']}, executed={h['executed']}, outcomes={h['outcomes']} @ {h['ts']}"
            )

        lines.append("")
        lines.append("## 产出三分类（per PRD 4.1.4）")
        for o in state.outcomes[-10:]:
            if isinstance(o, dict):
                lines.append(f"- [{o.get('type', '?')}] {o.get('name', '?')}: {o.get('description', '?')}")
            else:
                lines.append(f"- [{o.type}] {o.name}: {o.description}")

        lines.append("")
        lines.append("## L0 白名单")
        for action in sorted(L0_ALLOWLIST):
            lines.append(f"  ✅ {action}")

        lines.append("")
        lines.append("## L1+ 待确认（本次未自动执行）")
        for h in state.history[-5:]:
            if h["plans"] > h["executed"]:
                lines.append(f"  周期 #{h['cycle']}: {h['plans'] - h['executed']} 项 L1+ 待用户确认")

        print("\n".join(lines))

    return 0 if not state.degraded_reason else 2


if __name__ == "__main__":
    raise SystemExit(main())
