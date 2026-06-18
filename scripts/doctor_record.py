#!/usr/bin/env python3
"""Append a simple local case note for OpenClaw Doctor."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Record an OpenClaw Doctor case note")
    parser.add_argument("--case-dir", default=".doctor/cases")
    parser.add_argument("--title", required=True)
    parser.add_argument("--status", choices=["fixed", "partial", "blocked"], required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--symptom", default="")
    parser.add_argument("--diagnosis", default="")
    parser.add_argument("--action", default="")
    parser.add_argument("--verification", default="")
    parser.add_argument("--next", default="")
    args = parser.parse_args()

    case_dir = Path(args.case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    path = case_dir / f"{stamp}.md"
    entry = [
        f"## {datetime.now().isoformat(timespec='seconds')} - {args.title}",
        "",
        f"- 状态：{args.status}",
        f"- 摘要：{args.summary}",
        f"- 症状：{args.symptom}",
        f"- 诊断：{args.diagnosis}",
        f"- 执行动作：{args.action}",
        f"- 验证结果：{args.verification}",
        f"- 下次建议：{args.next}",
        "",
    ]
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(entry))
    print(str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
