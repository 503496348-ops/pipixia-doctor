#!/usr/bin/env python3
"""Search OpenClaw Doctor case notes."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class CaseHit:
    file: str
    title: str
    score: int
    excerpt: str


def split_cases(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^##\s+(.+)$", text, flags=re.MULTILINE))
    if not matches:
        return []
    cases: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        cases.append((match.group(1).strip(), text[start:end].strip()))
    return cases


def score_case(query: str, body: str) -> int:
    query_l = query.lower()
    body_l = body.lower()
    score = 0
    for token in re.findall(r"[\w\u4e00-\u9fff:/.-]{2,}", query_l):
        if token in body_l:
            score += 10 if len(token) >= 4 else 4
    return score


def excerpt(body: str, query: str) -> str:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    query_l = query.lower()
    for line in lines:
        if any(token in line.lower() for token in re.findall(r"[\w\u4e00-\u9fff:/.-]{2,}", query_l)):
            return line[:240]
    return " ".join(lines[:4])[:240]


def find_cases(case_dir: Path, query: str, limit: int) -> list[CaseHit]:
    hits: list[CaseHit] = []
    if not case_dir.exists():
        return hits
    for path in sorted(case_dir.glob("*.md"), reverse=True):
        text = path.read_text(encoding="utf-8", errors="replace")
        for title, body in split_cases(text):
            score = score_case(query, body)
            if score > 0 or not query:
                hits.append(CaseHit(str(path), title, score, excerpt(body, query)))
    hits.sort(key=lambda item: (item.score, item.file), reverse=True)
    return hits[:limit]


def render_markdown(hits: list[CaseHit], case_dir: Path, query: str) -> str:
    if not hits:
        return "\n".join(
            [
                "皮皮虾医生病历查询",
                "",
                "未找到匹配病历。",
                f"病历目录：{case_dir}",
                f"查询词：{query or '(空)'}",
                "",
                "下一步：先运行体检或药方匹配，修复后用 doctor_record.py 写入病历。",
            ]
        )
    lines = ["皮皮虾医生病历查询", "", f"查询词：{query or '(最近病历)'}", ""]
    for index, hit in enumerate(hits, 1):
        lines.extend(
            [
                f"{index}. {hit.title}",
                f"   匹配分：{hit.score}",
                f"   文件：{hit.file}",
                f"   摘要：{hit.excerpt}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Search OpenClaw Doctor case notes")
    parser.add_argument("--case-dir", default=".doctor/cases")
    parser.add_argument("--query", default="")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    case_dir = Path(args.case_dir)
    hits = find_cases(case_dir, args.query, args.limit)
    if args.format == "json":
        print(json.dumps({"case_dir": str(case_dir), "query": args.query, "hits": [asdict(hit) for hit in hits]}, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(hits, case_dir, args.query))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
