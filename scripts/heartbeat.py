#!/usr/bin/env python3
"""OpenClaw Doctor v5.0 — HEARTBEAT 主动预警引擎

Implements PRD 4.1.2 「自动预警」模块，集成到守夜人主 session 的 HEARTBEAT 系统。

Decisions (per evolution_gate/v5_decision_points.md):
- Option a: 新增独立 HEARTBEAT 通道，不破坏现有静默规则
- L1-L7 分级告警
- 连续 3 轮 error 触发熔断（按 PRD 4.1.2）
- 6h 无进化 强制熔断（与 PCEC 协同）

Channel design:
- L1-L2: 仅 metrics，不推送（兼容现有静默）
- L3-L4: 飞书私聊推送给守夜人
- L5-L7: 飞书群推送（必须）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# L1-L7 告警分级（与 PRD HEARTBEAT 章节对齐）
# ---------------------------------------------------------------------------
LEVELS = {
    "L1": "info — 仅记录，不推送",
    "L2": "notice — 仅记录，不推送",
    "L3": "warning — 私聊推送给守夜人",
    "L4": "error — 私聊推送给守夜人 + 飞书群",
    "L5": "critical — 飞书群 + 飞书@用户",
    "L6": "fatal — 飞书群 + 飞书@用户 + 邮件",
    "L7": "panic — 全部通道 + 触发熔断",
}


@dataclass
class Finding:
    """Single finding produced by a check."""

    check: str
    level: str
    title: str
    evidence: str
    next_step: str = ""


@dataclass
class HeartbeatState:
    """Maintains rolling state across rounds."""

    round_num: int = 0
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    consecutive_errors: int = 0
    last_evolution_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    alerts_log: list[dict] = field(default_factory=list)
    degraded: bool = False
    findings: list[Finding] = field(default_factory=list)

    def record(self, finding: Finding) -> None:
        self.findings.append(finding)
        if finding.level in ("L4", "L5", "L6", "L7"):
            self.alerts_log.append(
                {"ts": datetime.now().isoformat(timespec="seconds"), "level": finding.level, "title": finding.title}
            )


# ---------------------------------------------------------------------------
# 单轮检查（参考 doctor_check.py 已有逻辑）
# ---------------------------------------------------------------------------
def run_round(state: HeartbeatState, target: Path) -> HeartbeatState:
    """Run a single HEARTBEAT round and append findings."""
    state.round_num += 1
    state.findings = []

    # L1: 检查 SOUL/AGENTS/IDENTITY/USER/TOOLS.md
    for name in ["SOUL.md", "AGENTS.md", "IDENTITY.md", "USER.md", "TOOLS.md"]:
        if not (target / name).exists():
            state.record(Finding("core_files", "L3", f"缺少核心文件 {name}", str(target / name), "重新生成或恢复"))
        else:
            state.record(Finding("core_files", "L1", f"核心文件 {name} OK", str(target / name)))

    # L2: HEARTBEAT.md 时效性
    heartbeat_md = target / "HEARTBEAT.md"
    if heartbeat_md.exists():
        text = heartbeat_md.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"\| (\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}) \| ✅ HEARTBEAT_OK", text)
        if m:
            last_str = m.group(1)
            last = datetime.strptime(last_str, "%Y-%m-%d %H:%M")
            hours = (datetime.now() - last).total_seconds() / 3600
            if hours > 3:
                state.record(Finding("heartbeat_freshness", "L4", f"心跳超时 {hours:.1f}h", last_str, "检查 gateway 与 cron"))
            else:
                state.record(Finding("heartbeat_freshness", "L1", f"心跳新鲜 {hours:.1f}h", last_str))
        else:
            state.record(Finding("heartbeat_freshness", "L3", "未找到 HEARTBEAT_OK", str(heartbeat_md), "检查心跳格式"))
    else:
        state.record(Finding("heartbeat_freshness", "L5", "HEARTBEAT.md 缺失", str(heartbeat_md), "重新创建"))

    # L3: 内存（memory/）大小
    mem = target / "memory"
    if mem.exists():
        total = sum(f.stat().st_size for f in mem.rglob("*") if f.is_file())
        if total > 10 * 1024 * 1024:
            state.record(Finding("memory_size", "L3", f"memory/ 超过 10MB（{total // 1024}KB）", str(mem), "归档旧记忆"))
        else:
            state.record(Finding("memory_size", "L1", f"memory/ 健康 {total // 1024}KB", str(mem)))

    # L4: cron 任务健康
    cron_files = [target / "cron_tasks.json", target / "state" / "cron_tasks.json"]
    for cf in cron_files:
        if cf.exists():
            text = cf.read_text(encoding="utf-8", errors="replace").lower()
            if "error" in text or "fail" in text:
                state.record(Finding("cron_health", "L4", "cron 包含 error/fail", str(cf), "查看 cron 日志"))
            else:
                state.record(Finding("cron_health", "L1", "cron 健康", str(cf)))
            break

    # L5: 连续 3 轮 error → 熔断
    error_count = sum(1 for f in state.findings if f.level in ("L4", "L5", "L6", "L7"))
    if error_count >= 2:
        state.consecutive_errors += 1
        if state.consecutive_errors >= 3 and not state.degraded:
            state.degraded = True
            state.record(Finding("circuit_breaker", "L7", f"连续 3 轮 error 触发熔断", f"errors={state.consecutive_errors}", "进入降级模式"))
    else:
        state.consecutive_errors = 0

    # L6: 6h 无实质进化 → 强制熔断（与 PCEC 协同）
    if state.last_evolution_at:
        last_ev = datetime.fromisoformat(state.last_evolution_at)
        hours_since = (datetime.now() - last_ev).total_seconds() / 3600
        if hours_since > 6:
            state.record(Finding("evolution_stall", "L4", f"已 {hours_since:.1f}h 无实质进化", state.last_evolution_at, "触发 PCEC 强制审视"))

    return state


# ---------------------------------------------------------------------------
# 报告渲染
# ---------------------------------------------------------------------------
def render_report(state: HeartbeatState) -> str:
    by_level = Counter(f.level for f in state.findings)
    lines = [
        "🦐 皮皮虾医生 HEARTBEAT 主动预警报告",
        "",
        f"轮次: #{state.round_num}",
        f"启动: {state.started_at}",
        f"状态: {'🔴 DEGRADED（熔断）' if state.degraded else '🟢 健康'}",
        f"连续 error: {state.consecutive_errors}",
        "",
        "## 告警分布",
    ]
    for level in ("L7", "L6", "L5", "L4", "L3", "L2", "L1"):
        if by_level.get(level, 0) > 0:
            lines.append(f"- {level} ({LEVELS[level]}): {by_level[level]}")
    lines.append("")
    lines.append("## 详情")
    for f in state.findings:
        emoji = {"L7": "🚨", "L6": "💥", "L5": "🔥", "L4": "❌", "L3": "⚠️", "L2": "📝", "L1": "✅"}.get(f.level, "?")
        lines.append(f"- {emoji} [{f.level}] {f.check}: {f.title}")
        lines.append(f"  证据: {f.evidence}")
        if f.next_step:
            lines.append(f"  下一步: {f.next_step}")
    return "\n".join(lines)


def should_push_to_channel(finding: Finding) -> str:
    """按决策 a：L1-L2 静默（不推送），L3+ 推送"""
    if finding.level in ("L1", "L2"):
        return "silent"
    elif finding.level in ("L3", "L4"):
        return "feishu-pm"
    elif finding.level in ("L5", "L6", "L7"):
        return "feishu-group"
    return "silent"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="OpenClaw Doctor HEARTBEAT主动预警")
    parser.add_argument("--target", default=".", help="目标目录")
    parser.add_argument("--state-file", default="state/heartbeat_state.json", help="状态文件")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--rounds", type=int, default=1, help="连续跑多轮（测试用）")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    state_path = target / args.state_file if not Path(args.state_file).is_absolute() else Path(args.state_file)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    # 加载或初始化状态
    if state_path.exists():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            state = HeartbeatState(**{k: v for k, v in data.items() if k in HeartbeatState.__annotations__})
        except Exception:
            state = HeartbeatState()
    else:
        state = HeartbeatState()

    # 跑 N 轮
    for _ in range(args.rounds):
        state = run_round(state, target)

    # 保存
    state_path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")

    # 输出
    if args.format == "json":
        # 简化输出：不包含 dataclass 对象
        out = {
            "round": state.round_num,
            "degraded": state.degraded,
            "consecutive_errors": state.consecutive_errors,
            "alerts_count": len(state.alerts_log),
            "findings": [asdict(f) for f in state.findings],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(render_report(state))

    # 按推送通道分级
    push_summary = Counter(should_push_to_channel(f) for f in state.findings)
    print(f"\n## 推送通道分布")
    for ch, cnt in push_summary.items():
        print(f"  {ch}: {cnt}")

    return 0 if not state.degraded else 2


if __name__ == "__main__":
    raise SystemExit(main())
