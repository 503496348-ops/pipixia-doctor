#!/usr/bin/env python3
"""Route Feishu message text to OpenClaw Doctor actions.

This is a local router for bot integration tests. It does not call Feishu APIs.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict


@dataclass
class Route:
    intent: str
    action: str
    command: list[str]
    confirmation_required: bool
    reply_hint: str


def strip_prefix(text: str) -> str:
    for prefix in ["皮皮虾医生", "openclaw doctor", "OpenClaw Doctor", "@皮皮虾医生"]:
        if text.strip().lower().startswith(prefix.lower()):
            return text.strip()[len(prefix) :].strip(" ：:\n\t")
    return text.strip()


def route(text: str) -> Route:
    body = strip_prefix(text)
    lowered = body.lower()
    if any(word in body for word in ["体检", "看看状态", "系统检查", "健康"]):
        return Route("health_check", "run_health_check", ["python3", "openclaw-doctor/scripts/doctor_check.py", "--target", ".", "--format", "markdown"], False, "返回健康报告。")
    if any(word in body for word in ["上次", "历史", "病历", "怎么处理"]):
        query = body or text
        return Route("case_search", "search_cases", ["python3", "openclaw-doctor/scripts/case_search.py", "--query", query], False, "返回匹配病历。")
    if any(word in body for word in ["修一下", "修复", "自愈", "帮我处理"]):
        symptom = body.split("：", 1)[-1].strip() if "：" in body else body
        return Route("repair_plan", "generate_repair_plan", ["python3", "openclaw-doctor/scripts/repair_plan.py", "--text", symptom], True, "先返回修复计划，等待用户确认。")
    if any(word in body for word in ["报错", "出错", "故障", "坏了"]) or "\n" in body:
        symptom = body.split("：", 1)[-1].strip() if "：" in body else body
        return Route("prescription_match", "match_prescription", ["python3", "openclaw-doctor/scripts/prescription_match.py", "--text", symptom], False, "返回药方卡。")
    if any(word in body for word in ["开始", "引导", "不会用", "带我上手"]):
        return Route("onboarding", "read_beginner_guide", ["open", "openclaw-doctor/references/beginner_guide.md"], False, "按小白引导回复，不直接执行外部操作。")
    return Route("fallback", "fallback_report", ["python3", "openclaw-doctor/scripts/doctor_check.py", "--target", ".", "--format", "markdown"], False, "未识别明确意图，先做只读体检或请用户贴报错。")


def main() -> int:
    parser = argparse.ArgumentParser(description="Route a Feishu message to an OpenClaw Doctor action")
    parser.add_argument("--text", required=True)
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()
    result = route(args.text)
    if args.format == "json":
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    else:
        print("飞书消息路由")
        print("")
        print(f"意图：{result.intent}")
        print(f"动作：{result.action}")
        print(f"命令：{' '.join(result.command)}")
        print(f"需要确认：{'是' if result.confirmation_required else '否'}")
        print(f"回复提示：{result.reply_hint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
