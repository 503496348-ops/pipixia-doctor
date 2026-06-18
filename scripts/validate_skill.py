#!/usr/bin/env python3
"""Dependency-free structure validator for this skill package."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$")


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill_dir", nargs="?", default=".")
    args = parser.parse_args()
    # 🔧 UAT修复: resolve() 支持相对路径
    root = Path(args.skill_dir).resolve()
    errors: list[str] = []
    skill_md = root / "SKILL.md"
    if not skill_md.exists():
        errors.append("missing SKILL.md")
    else:
        meta = parse_frontmatter(skill_md.read_text(encoding="utf-8", errors="replace"))
        name = meta.get("name", "")
        description = meta.get("description", "")
        if not NAME_RE.match(name):
            errors.append(f"invalid name: {name!r}")
        if name != root.name:
            errors.append(f"name does not match folder: {name!r} != {root.name!r}")
        if len(description) < 80 or "TODO" in description:
            errors.append("description is too short or still TODO")
    openai_yaml = root / "agents" / "openai.yaml"
    if openai_yaml.exists():
        text = openai_yaml.read_text(encoding="utf-8", errors="replace")
        if f"${root.name}" not in text:
            errors.append("agents/openai.yaml default_prompt must mention $skill-name")
    for rel in [
        "README.md",
        "USER_MANUAL.md",
        "references/prescriptions.md",
        "references/safety_policy.md",
        "references/output_formats.md",
        "references/prd_summary.md",
        "references/beginner_guide.md",
        "references/test_cases.md",
        "references/workflow_guide.md",
        "references/feishu_bot_handler.md",
        "scripts/doctor_check.py",
        "scripts/prescription_match.py",
        "scripts/repair_plan.py",
        "scripts/case_search.py",
        "scripts/feishu_route.py",
        "scripts/doctor_record.py",
    ]:
        if not (root / rel).exists():
            errors.append(f"missing {rel}")
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
