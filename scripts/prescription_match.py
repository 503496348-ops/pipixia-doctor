#!/usr/bin/env python3
"""Match pasted errors to OpenClaw Doctor prescriptions."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class Prescription:
    rx_id: str
    symptoms: str
    diagnosis: str
    prescription: str
    risk: str


def load_prescriptions(path: Path) -> list[Prescription]:
    rows: list[Prescription] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("| RX-"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        rows.append(Prescription(cells[0], cells[1], cells[2], cells[3], cells[4]))
    return rows


STOPWORDS = {
    "and",
    "the",
    "with",
    "none",
    "not",
    "fail",
    "failed",
    "error",
    "missing",
    "invalid",
    "file",
    "path",
    "token",
}


def tokens(text: str) -> list[str]:
    raw = re.findall(r"`([^`]+)`|([A-Za-z0-9_:/.-]{3,})", text)
    values = []
    for quoted, bare in raw:
        value = (quoted or bare).strip().lower()
        if value and value not in STOPWORDS:
            values.append(value)
    return values


def has_non_ascii(value: str) -> bool:
    return any(ord(char) > 127 for char in value)


def score_match(query: str, item: Prescription) -> tuple[int, list[str]]:
    haystack = f"{item.rx_id} {item.symptoms} {item.diagnosis} {item.prescription}".lower()
    query_l = query.lower()
    query_tokens = set(tokens(query))
    matched: list[str] = []
    score = 0
    if "modulenotfounderror" in query_l or "no module named" in query_l:
        if item.rx_id == "RX-SKILL-005" and any(word in query_l for word in ["yaml", "pyyaml", "yml"]):
            score += 70
            matched.append("yaml module missing")
        elif item.rx_id == "RX-DEP-003" and not any(word in query_l for word in ["yaml", "pyyaml", "yml"]):
            score += 70
            matched.append("ModuleNotFoundError")
    if item.rx_id.lower() in query_l:
        score += 100
        matched.append(item.rx_id)
    for token in tokens(item.symptoms):
        if (" " in token and token in query_l) or has_non_ascii(token) and token in query_l or token in query_tokens:
            score += 20 if len(token) > 8 else 10
            matched.append(token)
    for token in tokens(query):
        if token in haystack:
            score += 4
    return score, sorted(set(matched))


def render_markdown(matches: list[tuple[int, list[str], Prescription]], query: str) -> str:
    lines = ["皮皮虾医生药方匹配", ""]
    if not matches or matches[0][0] <= 0:
        return "\n".join(
            [
                "皮皮虾医生药方匹配",
                "",
                "未找到明确药方。",
                "",
                "建议：",
                "1. 先运行只读体检。",
                "2. 摘取最关键的 20 行错误日志。",
                "3. 生成兜底诊断报告，等待人工确认后再新增药方。",
                "",
                f"输入摘要：{query[:500]}",
            ]
        )
    for rank, (score, matched, item) in enumerate(matches[:3], 1):
        lines.extend(
            [
                f"{rank}. 药方：{item.rx_id}",
                f"   匹配分：{score}",
                f"   命中症状：{', '.join(matched) if matched else '语义/关键词弱匹配'}",
                f"   小白解释：{item.diagnosis}",
                f"   修复步骤：{item.prescription}",
                f"   风险等级：{item.risk}",
                "",
            ]
        )
    lines.append("下一步：按最高匹配药方处理；涉及写入、安装、授权或删除时先确认。")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Match error text to OpenClaw Doctor prescriptions")
    parser.add_argument("--text", default="", help="error text to match")
    parser.add_argument("--file", help="read error text from file")
    parser.add_argument("--prescriptions", default=str(Path(__file__).resolve().parents[1] / "references" / "prescriptions.md"))
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    query = args.text
    if args.file:
        query = Path(args.file).read_text(encoding="utf-8", errors="replace")
    items = load_prescriptions(Path(args.prescriptions))
    matches = sorted(((score_match(query, item)[0], score_match(query, item)[1], item) for item in items), key=lambda row: row[0], reverse=True)
    threshold = 8
    matches = [row for row in matches if row[0] >= threshold]
    if matches:
        relative_threshold = max(threshold, int(matches[0][0] * 0.35))
        matches = [row for row in matches if row[0] >= relative_threshold]
    if args.format == "json":
        print(json.dumps({"query": query[:1000], "matches": [{"score": s, "matched": m, **asdict(p)} for s, m, p in matches[:5]]}, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(matches, query))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
