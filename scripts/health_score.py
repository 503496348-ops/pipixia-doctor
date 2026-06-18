#!/usr/bin/env python3
"""OpenClaw Doctor v5.0 — Health Score 基线 + 熔断自动恢复

Implements PRD 3.3 「自适应阈值机制」:
- Health Score 基线（10 次均值）
- 异常信号 ≥15 分降级
- 超出预期 ≥10 分正反馈
- 连续 3 轮 error 触发熔断
- 6h 无进化熔断
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# PRD 3.3 自适应阈值
# ---------------------------------------------------------------------------
THRESHOLD = {
    "baseline_window": 10,          # 基线窗口：最近 10 次
    "downgrade_delta": -15,         # 异常信号阈值（低于基线 15 分降级）
    "upgrade_delta": 10,            # 正反馈阈值（高于基线 10 分升级）
    "circuit_breaker_errors": 3,    # 连续 error 触发熔断
    "evolution_stall_hours": 6,     # 6h 无进化熔断
    "recover_streak": 3,            # 连续 3 轮 ok 自动恢复
}


@dataclass
class HealthState:
    """Health Score engine state."""

    score_history: list[dict] = field(default_factory=list)  # [{ts, score, status}, ...]
    baseline: float = 0.0
    current_score: int = 0
    consecutive_errors: int = 0
    consecutive_ok: int = 0
    degraded: bool = False
    degrade_reason: str = ""
    last_evolution_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    state_path: str = ""

    def add_score(self, score: int, status: str) -> None:
        self.score_history.append({"ts": datetime.now().isoformat(timespec="seconds"), "score": score, "status": status})
        # 只保留最近 50 个
        self.score_history = self.score_history[-50:]
        self.current_score = score

    def compute_baseline(self) -> float:
        if not self.score_history:
            return 0.0
        recent = [h["score"] for h in self.score_history[-THRESHOLD["baseline_window"]:]]
        self.baseline = statistics.mean(recent) if recent else 0.0
        return self.baseline

    def should_downgrade(self) -> bool:
        if self.baseline == 0:
            return False
        delta = self.current_score - self.baseline
        return delta <= THRESHOLD["downgrade_delta"]

    def should_upgrade(self) -> bool:
        if not self.degraded or self.baseline == 0:
            return False
        delta = self.current_score - self.baseline
        return delta >= THRESHOLD["upgrade_delta"]

    def should_circuit_break(self) -> bool:
        return self.consecutive_errors >= THRESHOLD["circuit_breaker_errors"]

    def should_recover(self) -> bool:
        return self.degraded and self.consecutive_ok >= THRESHOLD["recover_streak"]

    def should_stall(self) -> bool:
        if not self.last_evolution_at:
            return False
        last = datetime.fromisoformat(self.last_evolution_at)
        hours_since = (datetime.now() - last).total_seconds() / 3600
        return hours_since > THRESHOLD["evolution_stall_hours"]


def evaluate_round(state: HealthState, score: int, status: str) -> HealthState:
    """评估新一轮健康分，更新状态。"""
    state.add_score(score, status)
    state.compute_baseline()

    # 错误计数
    if status in ("error", "critical", "fatal"):
        state.consecutive_errors += 1
        state.consecutive_ok = 0
    elif status in ("ok", "healthy"):
        state.consecutive_ok += 1
        state.consecutive_errors = 0
    else:
        # warn 类不重置计数
        pass

    # 降级判断
    if state.should_downgrade():
        if not state.degraded:
            state.degraded = True
            state.degrade_reason = f"score={state.current_score} 低于基线 {state.baseline:.1f} 超过 {abs(THRESHOLD['downgrade_delta'])}"

    # 升级判断
    if state.should_upgrade():
        state.degraded = False
        state.degrade_reason = ""

    # 熔断判断
    if state.should_circuit_break():
        state.degraded = True
        state.degrade_reason = f"连续 {state.consecutive_errors} 轮 error 触发熔断"

    # 进化停滞
    if state.should_stall():
        state.degraded = True
        if "进化停滞" not in state.degrade_reason:
            state.degrade_reason += f" + {THRESHOLD['evolution_stall_hours']}h+ 无进化"

    # 自动恢复
    if state.should_recover():
        state.degraded = False
        state.degrade_reason = f"连续 {THRESHOLD['recover_streak']} 轮 ok 自动恢复"

    # 成功事件 = 进化（每次 ok 算一次小进化）
    if status in ("ok", "healthy"):
        state.last_evolution_at = datetime.now().isoformat(timespec="seconds")

    return state


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenClaw Doctor Health Score 基线引擎")
    parser.add_argument("--score", type=int, default=68, help="当前健康分")
    parser.add_argument("--status", default="warn", help="当前状态 (ok/warn/error/critical/fatal)")
    parser.add_argument("--rounds", type=int, default=1, help="连续跑多轮")
    parser.add_argument("--state-file", default="state/health_score_state.json")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    state_path = Path(args.state_file)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    # 加载
    if state_path.exists():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            valid_fields = {k: v for k, v in data.items() if k in HealthState.__annotations__}
            state = HealthState(**valid_fields)
        except Exception:
            state = HealthState()
    else:
        state = HealthState()

    # 跑 N 轮
    for _ in range(args.rounds):
        state = evaluate_round(state, args.score, args.status)

    # 保存
    state_path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")

    # 输出
    if args.format == "json":
        print(json.dumps(asdict(state), ensure_ascii=False, indent=2))
    else:
        lines = [
            "🦐 皮皮虾医生 Health Score 基线引擎",
            "",
            f"当前健康分: {state.current_score}",
            f"基线（最近 10 次均值）: {state.baseline:.1f}",
            f"状态: {'🔴 ' + state.degrade_reason if state.degraded else '🟢 健康'}",
            f"连续 error: {state.consecutive_errors}",
            f"连续 ok: {state.consecutive_ok}",
            f"最近进化: {state.last_evolution_at}",
            "",
            "## 阈值配置（per PRD 3.3）",
            f"  基线窗口: {THRESHOLD['baseline_window']} 次",
            f"  降级阈值: 低于基线 {abs(THRESHOLD['downgrade_delta'])} 分",
            f"  升级阈值: 高于基线 {THRESHOLD['upgrade_delta']} 分",
            f"  熔断: 连续 {THRESHOLD['circuit_breaker_errors']} 轮 error",
            f"  进化停滞: {THRESHOLD['evolution_stall_hours']}h+ 无进化",
            f"  自动恢复: 连续 {THRESHOLD['recover_streak']} 轮 ok",
            "",
            "## 最近 10 个分数",
        ]
        for h in state.score_history[-10:]:
            emoji = {"ok": "🟢", "warn": "🟡", "error": "🔴", "critical": "🔥", "fatal": "💥"}.get(h["status"], "?")
            lines.append(f"  {emoji} {h['score']} ({h['status']}) @ {h['ts']}")
        print("\n".join(lines))

    return 0 if not state.degraded else 2


if __name__ == "__main__":
    raise SystemExit(main())
