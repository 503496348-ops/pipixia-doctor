#!/usr/bin/env python3
"""OpenClaw Doctor v5.1 — 药方自学习引擎 (Prescription Self-Learning)

Implements feedback-driven prescription improvement:
- Track prescription match outcomes (hit/miss/effective/ineffective)
- Analyze case patterns to suggest new prescriptions
- Score prescription effectiveness over time
- Auto-generate prescription candidates from resolved cases
- Detect recurring issues that need new prescriptions

Design:
- Feedback log: .doctor/rx_feedback.jsonl (append-only)
- Effectiveness scores: computed from feedback log
- New prescription candidates: generated from unmatched resolved cases
- Pattern detection: cluster similar unresolved errors

Brand: AtomCollide-智械工坊
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FEEDBACK_LOG = ".doctor/rx_feedback.jsonl"
CANDIDATES_FILE = ".doctor/rx_candidates.json"
EFFECTIVENESS_FILE = ".doctor/rx_effectiveness.json"

# Minimum feedback count before we compute effectiveness
MIN_FEEDBACK_FOR_SCORING = 3

# Threshold for flagging an ineffective prescription
INEFFECTIVE_THRESHOLD = 0.3  # <30% success rate

# Threshold for auto-promoting a candidate to prescription
CANDIDATE_PROMOTE_THRESHOLD = 3  # seen 3+ times as unresolved


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FeedbackEntry:
    """A single feedback record for a prescription match."""
    timestamp: str
    rx_id: str
    query_text: str
    match_score: int
    outcome: str  # hit | miss | effective | ineffective | skipped
    resolved: bool
    resolution_notes: str = ""
    case_id: str = ""


@dataclass
class PrescriptionScore:
    """Effectiveness score for a prescription."""
    rx_id: str
    total_matches: int = 0
    hits: int = 0
    misses: int = 0
    effective: int = 0
    ineffective: int = 0
    success_rate: float = 0.0
    last_matched: str = ""
    trending: str = "stable"  # improving | declining | stable


@dataclass
class CandidateRx:
    """A candidate prescription suggested by the learning engine."""
    candidate_id: str
    suggested_symptoms: str
    suggested_diagnosis: str
    suggested_prescription: str
    suggested_risk: str = "L1"
    source_cases: list[str] = field(default_factory=list)
    occurrence_count: int = 0
    first_seen: str = ""
    last_seen: str = ""
    keyword_pattern: str = ""


# ---------------------------------------------------------------------------
# Feedback tracking
# ---------------------------------------------------------------------------

def record_feedback(
    rx_id: str,
    query_text: str,
    match_score: int,
    outcome: str,
    resolved: bool,
    resolution_notes: str = "",
    case_id: str = "",
) -> dict:
    """Record a feedback entry for a prescription match."""
    entry = FeedbackEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        rx_id=rx_id,
        query_text=query_text[:500],
        match_score=match_score,
        outcome=outcome,
        resolved=resolved,
        resolution_notes=resolution_notes[:500],
        case_id=case_id,
    )
    return asdict(entry)


def append_feedback(target: Path, entry: dict) -> Path:
    """Append a feedback entry to the log."""
    log_path = target / FEEDBACK_LOG
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return log_path


def load_feedback(target: Path) -> list[dict]:
    """Load all feedback entries."""
    log_path = target / FEEDBACK_LOG
    if not log_path.exists():
        return []
    entries = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


# ---------------------------------------------------------------------------
# Effectiveness scoring
# ---------------------------------------------------------------------------

def compute_effectiveness(target: Path) -> list[PrescriptionScore]:
    """Compute effectiveness scores for all prescriptions."""
    entries = load_feedback(target)

    # Group by rx_id
    by_rx: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        rx_id = entry.get("rx_id", "unknown")
        by_rx[rx_id].append(entry)

    scores: list[PrescriptionScore] = []
    for rx_id, rx_entries in by_rx.items():
        score = PrescriptionScore(rx_id=rx_id)
        score.total_matches = len(rx_entries)

        for entry in rx_entries:
            outcome = entry.get("outcome", "miss")
            if outcome == "hit":
                score.hits += 1
            elif outcome == "miss":
                score.misses += 1
            elif outcome == "effective":
                score.effective += 1
            elif outcome == "ineffective":
                score.ineffective += 1

        # Success rate = (hits + effective) / total
        successes = score.hits + score.effective
        if score.total_matches > 0:
            score.success_rate = round(successes / score.total_matches, 3)

        # Last matched timestamp
        if rx_entries:
            score.last_matched = max(e.get("timestamp", "") for e in rx_entries)

        # Trending: compare last 3 vs first 3 outcomes
        if len(rx_entries) >= 6:
            first_half = rx_entries[:len(rx_entries)//2]
            second_half = rx_entries[len(rx_entries)//2:]
            first_rate = sum(1 for e in first_half if e.get("outcome") in ("hit", "effective")) / len(first_half)
            second_rate = sum(1 for e in second_half if e.get("outcome") in ("hit", "effective")) / len(second_half)
            if second_rate > first_rate + 0.2:
                score.trending = "improving"
            elif second_rate < first_rate - 0.2:
                score.trending = "declining"

        scores.append(score)

    # Sort by total matches descending
    scores.sort(key=lambda s: s.total_matches, reverse=True)
    return scores


# ---------------------------------------------------------------------------
# Candidate prescription generation
# ---------------------------------------------------------------------------

def extract_keywords(text: str) -> list[str]:
    """Extract significant keywords from error text."""
    # Remove common noise
    noise = {"error", "failed", "failure", "exception", "the", "and", "with", "for", "not", "was", "are"}
    # Split on non-alphanumeric and get tokens >= 3 chars
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_.]{2,}", text)
    chinese = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    all_tokens = [t.lower() for t in tokens if t.lower() not in noise] + chinese
    return list(dict.fromkeys(all_tokens))  # dedupe preserving order


def cluster_unmatched_errors(target: Path) -> list[CandidateRx]:
    """Analyze feedback log for recurring unmatched errors → prescription candidates."""
    entries = load_feedback(target)

    # Find entries where outcome was "miss" (no good prescription match)
    missed = [e for e in entries if e.get("outcome") == "miss" and not e.get("resolved")]

    if not missed:
        return []

    # Cluster by keyword overlap
    clusters: dict[str, list[dict]] = {}  # keyword_signature -> [entries]
    for entry in missed:
        query = entry.get("query_text", "")
        keywords = extract_keywords(query)
        if not keywords:
            continue
        # Use top 3 keywords as cluster key
        signature = "|".join(sorted(keywords[:3]))
        clusters.setdefault(signature, []).append(entry)

    candidates: list[CandidateRx] = []
    cand_idx = 0
    for signature, cluster_entries in clusters.items():
        if len(cluster_entries) < 1:  # At least 1 occurrence to be a candidate
            continue

        cand_idx += 1
        # Merge keywords from all entries in cluster
        all_keywords: list[str] = []
        for e in cluster_entries:
            all_keywords.extend(extract_keywords(e.get("query_text", "")))

        keyword_freq = Counter(all_keywords)
        top_keywords = [w for w, _ in keyword_freq.most_common(8)]

        # Generate candidate
        candidate = CandidateRx(
            candidate_id=f"RX-CAND-{cand_idx:03d}",
            suggested_symptoms=", ".join(top_keywords[:5]),
            suggested_diagnosis=f"反复出现的未匹配错误模式（关键词: {', '.join(top_keywords[:3])}）",
            suggested_prescription=f"待人工补充。关键词: {', '.join(top_keywords)}",
            suggested_risk="L1",
            source_cases=[e.get("case_id", "") for e in cluster_entries if e.get("case_id")],
            occurrence_count=len(cluster_entries),
            first_seen=min(e.get("timestamp", "") for e in cluster_entries),
            last_seen=max(e.get("timestamp", "") for e in cluster_entries),
            keyword_pattern=signature,
        )
        candidates.append(candidate)

    # Sort by occurrence count descending
    candidates.sort(key=lambda c: c.occurrence_count, reverse=True)
    return candidates


def generate_from_resolved_cases(target: Path) -> list[CandidateRx]:
    """Generate prescription candidates from resolved cases that had no good match."""
    entries = load_feedback(target)

    # Find resolved entries with miss/ineffective outcome
    resolved_misses = [
        e for e in entries
        if e.get("resolved") and e.get("outcome") in ("miss", "ineffective") and e.get("resolution_notes")
    ]

    candidates: list[CandidateRx] = []
    for i, entry in enumerate(resolved_misses, 1):
        query = entry.get("query_text", "")
        resolution = entry.get("resolution_notes", "")
        keywords = extract_keywords(query)

        candidate = CandidateRx(
            candidate_id=f"RX-RESOLVED-{i:03d}",
            suggested_symptoms=", ".join(keywords[:5]),
            suggested_diagnosis=f"用户手动解决: {resolution[:200]}",
            suggested_prescription=resolution[:500],
            suggested_risk="L1",
            source_cases=[entry.get("case_id", "")] if entry.get("case_id") else [],
            occurrence_count=1,
            first_seen=entry.get("timestamp", ""),
            last_seen=entry.get("timestamp", ""),
            keyword_pattern="|".join(sorted(keywords[:3])),
        )
        candidates.append(candidate)

    return candidates


# ---------------------------------------------------------------------------
# Prescription gap analysis
# ---------------------------------------------------------------------------

def analyze_gaps(target: Path) -> dict:
    """Analyze prescription coverage gaps."""
    entries = load_feedback(target)

    if not entries:
        return {
            "total_feedback": 0,
            "gaps": [],
            "summary": "暂无反馈数据。使用 feedback 命令开始收集。",
        }

    # Overall stats
    total = len(entries)
    outcomes = Counter(e.get("outcome", "unknown") for e in entries)
    resolved = sum(1 for e in entries if e.get("resolved"))

    # Miss rate by rx_id
    by_rx: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        by_rx[e.get("rx_id", "unknown")].append(e)

    ineffective_rxs = []
    for rx_id, rx_entries in by_rx.items():
        if len(rx_entries) < MIN_FEEDBACK_FOR_SCORING:
            continue
        miss_rate = sum(1 for e in rx_entries if e.get("outcome") in ("miss", "ineffective")) / len(rx_entries)
        if miss_rate > (1 - INEFFECTIVE_THRESHOLD):
            ineffective_rxs.append({
                "rx_id": rx_id,
                "total_matches": len(rx_entries),
                "miss_rate": round(miss_rate, 3),
                "last_matched": max(e.get("timestamp", "") for e in rx_entries),
            })

    # Unresolved recurring patterns
    unresolved = [e for e in entries if not e.get("resolved") and e.get("outcome") == "miss"]
    unresolved_keywords: list[str] = []
    for e in unresolved:
        unresolved_keywords.extend(extract_keywords(e.get("query_text", "")))
    top_unresolved = Counter(unresolved_keywords).most_common(10)

    return {
        "total_feedback": total,
        "outcome_distribution": dict(outcomes),
        "resolved_count": resolved,
        "resolution_rate": round(resolved / total, 3) if total > 0 else 0,
        "ineffective_prescriptions": ineffective_rxs,
        "top_unresolved_keywords": top_unresolved,
        "gaps": ineffective_rxs,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_effectiveness(scores: list[PrescriptionScore]) -> str:
    """Render prescription effectiveness report."""
    if not scores:
        return "🦐 皮皮虾医生 药方效果报告\n\n暂无反馈数据。使用 feedback 命令开始收集。"

    lines = [
        "🦐 皮皮虾医生 药方效果报告",
        "",
        f"共 {len(scores)} 个药方有效果数据：",
        "",
    ]

    # Categorize
    effective = [s for s in scores if s.success_rate >= 0.7 and s.total_matches >= MIN_FEEDBACK_FOR_SCORING]
    moderate = [s for s in scores if 0.3 <= s.success_rate < 0.7 and s.total_matches >= MIN_FEEDBACK_FOR_SCORING]
    ineffective = [s for s in scores if s.success_rate < 0.3 and s.total_matches >= MIN_FEEDBACK_FOR_SCORING]
    insufficient = [s for s in scores if s.total_matches < MIN_FEEDBACK_FOR_SCORING]

    if effective:
        lines.append("## ✅ 高效药方 (成功率 ≥ 70%)")
        for s in effective:
            trend_emoji = {"improving": "📈", "declining": "📉", "stable": "➡️"}.get(s.trending, "?")
            lines.append(f"  - {s.rx_id}: {s.success_rate:.0%} ({s.total_matches}次) {trend_emoji}")
        lines.append("")

    if moderate:
        lines.append("## ⚠️ 中等药方 (30% ≤ 成功率 < 70%)")
        for s in moderate:
            trend_emoji = {"improving": "📈", "declining": "📉", "stable": "➡️"}.get(s.trending, "?")
            lines.append(f"  - {s.rx_id}: {s.success_rate:.0%} ({s.total_matches}次) {trend_emoji}")
        lines.append("")

    if ineffective:
        lines.append("## ❌ 低效药方 (成功率 < 30%)")
        for s in ineffective:
            lines.append(f"  - {s.rx_id}: {s.success_rate:.0%} ({s.total_matches}次) — 建议优化或替换")
        lines.append("")

    if insufficient:
        lines.append(f"## 📊 数据不足 ({len(insufficient)} 个药方)")
        for s in insufficient[:5]:
            lines.append(f"  - {s.rx_id}: {s.total_matches}/{MIN_FEEDBACK_FOR_SCORING} 次反馈")
        if len(insufficient) > 5:
            lines.append(f"  ... 还有 {len(insufficient) - 5} 个")
        lines.append("")

    return "\n".join(lines)


def render_candidates(candidates: list[CandidateRx], source: str = "unmatched") -> str:
    """Render prescription candidates."""
    if not candidates:
        return "🦐 皮皮虾医生 药方候选\n\n暂无候选药方建议。"

    title = "反复出现的未匹配错误" if source == "unmatched" else "用户手动解决的案例"
    lines = [
        f"🦐 皮皮虾医生 药方候选（{title}）",
        "",
        f"共 {len(candidates)} 个候选：",
        "",
    ]

    for cand in candidates[:10]:
        lines.extend([
            f"### {cand.candidate_id}",
            f"  症状关键词：{cand.suggested_symptoms}",
            f"  诊断：{cand.suggested_diagnosis}",
            f"  建议药方：{cand.suggested_prescription}",
            f"  风险等级：{cand.suggested_risk}",
            f"  出现次数：{cand.occurrence_count}",
            f"  首次出现：{cand.first_seen}",
            f"  末次出现：{cand.last_seen}",
            "",
        ])

    lines.append("下一步：人工审核后添加到 references/prescriptions.md。")
    return "\n".join(lines)


def render_gaps(gap_analysis: dict) -> str:
    """Render gap analysis report."""
    lines = [
        "🦐 皮皮虾医生 药方覆盖率分析",
        "",
        f"总反馈数：{gap_analysis.get('total_feedback', 0)}",
        f"已解决数：{gap_analysis.get('resolved_count', 0)}",
        f"解决率：{gap_analysis.get('resolution_rate', 0):.0%}",
        "",
    ]

    dist = gap_analysis.get("outcome_distribution", {})
    if dist:
        lines.append("## 结果分布")
        for outcome, count in dist.items():
            lines.append(f"  - {outcome}: {count}")
        lines.append("")

    ineffective = gap_analysis.get("ineffective_prescriptions", [])
    if ineffective:
        lines.append("## ⚠️ 低效药方（需优化）")
        for rx in ineffective:
            lines.append(f"  - {rx['rx_id']}: {rx['miss_rate']:.0%} 失败率 ({rx['total_matches']}次)")
        lines.append("")

    unresolved = gap_analysis.get("top_unresolved_keywords", [])
    if unresolved:
        lines.append("## 🔍 未解决高频关键词")
        for keyword, count in unresolved:
            lines.append(f"  - {keyword}: {count}次")
        lines.append("")

    if not ineffective and not unresolved:
        lines.append("✅ 当前药方覆盖率良好，无明显缺口。")

    return "\n".join(lines)


def render_report(target: Path) -> str:
    """Render the full self-learning report."""
    scores = compute_effectiveness(target)
    candidates_cluster = cluster_unmatched_errors(target)
    candidates_resolved = generate_from_resolved_cases(target)
    gaps = analyze_gaps(target)

    sections = [
        render_effectiveness(scores),
        "",
        "---",
        "",
        render_candidates(candidates_cluster, "unmatched"),
        "",
        "---",
        "",
        render_candidates(candidates_resolved, "resolved"),
        "",
        "---",
        "",
        render_gaps(gaps),
    ]
    return "\n".join(sections)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="OpenClaw Doctor 药方自学习引擎"
    )
    parser.add_argument("--target", default=".", help="Agent workspace directory")
    parser.add_argument(
        "--mode",
        choices=["feedback", "effectiveness", "candidates", "gaps", "report"],
        default="report",
        help="Operation mode",
    )
    # Feedback mode options
    parser.add_argument("--rx-id", default="", help="Prescription ID for feedback")
    parser.add_argument("--query", default="", help="Original query text")
    parser.add_argument("--score", type=int, default=0, help="Match score")
    parser.add_argument("--outcome", choices=["hit", "miss", "effective", "ineffective", "skipped"], default="miss")
    parser.add_argument("--resolved", action="store_true", help="Was the issue resolved?")
    parser.add_argument("--resolution", default="", help="How was it resolved?")
    parser.add_argument("--case-id", default="", help="Related case ID")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    target = Path(args.target).resolve()

    if args.mode == "feedback":
        if not args.rx_id or not args.query:
            print("ERROR: --rx-id and --query are required for feedback mode")
            return 1
        entry = record_feedback(
            rx_id=args.rx_id,
            query_text=args.query,
            match_score=args.score,
            outcome=args.outcome,
            resolved=args.resolved,
            resolution_notes=args.resolution,
            case_id=args.case_id,
        )
        append_feedback(target, entry)
        if args.format == "json":
            print(json.dumps(entry, ensure_ascii=False, indent=2))
        else:
            print("🦐 皮皮虾医生 反馈已记录")
            print(f"  药方：{args.rx_id}")
            print(f"  结果：{args.outcome}")
            print(f"  已解决：{'是' if args.resolved else '否'}")
            if args.resolution:
                print(f"  解决方案：{args.resolution[:100]}")
        return 0

    elif args.mode == "effectiveness":
        scores = compute_effectiveness(target)
        if args.format == "json":
            print(json.dumps([asdict(s) for s in scores], ensure_ascii=False, indent=2))
        else:
            print(render_effectiveness(scores))
        return 0

    elif args.mode == "candidates":
        cluster_cands = cluster_unmatched_errors(target)
        resolved_cands = generate_from_resolved_cases(target)
        all_cands = cluster_cands + resolved_cands
        if args.format == "json":
            print(json.dumps([asdict(c) for c in all_cands], ensure_ascii=False, indent=2))
        else:
            print(render_candidates(cluster_cands, "unmatched"))
            print("")
            print(render_candidates(resolved_cands, "resolved"))
        return 0

    elif args.mode == "gaps":
        gaps = analyze_gaps(target)
        if args.format == "json":
            print(json.dumps(gaps, ensure_ascii=False, indent=2))
        else:
            print(render_gaps(gaps))
        return 0

    elif args.mode == "report":
        if args.format == "json":
            scores = compute_effectiveness(target)
            candidates = cluster_unmatched_errors(target)
            resolved_cands = generate_from_resolved_cases(target)
            gaps = analyze_gaps(target)
            print(json.dumps({
                "effectiveness": [asdict(s) for s in scores],
                "candidates_from_unmatched": [asdict(c) for c in candidates],
                "candidates_from_resolved": [asdict(c) for c in resolved_cands],
                "gap_analysis": gaps,
            }, ensure_ascii=False, indent=2))
        else:
            print(render_report(target))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
