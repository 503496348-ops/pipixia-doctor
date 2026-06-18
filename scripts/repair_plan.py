#!/usr/bin/env python3
"""Generate a safe repair plan from an error or prescription ID.

This script never writes project files and never runs repair commands. It only
turns a matched prescription into a confirmation-ready plan.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prescription_match import Prescription, load_prescriptions, score_match  # noqa: E402


RISK_POLICY = {
    "L0": "可自动执行，只读检查或报告生成。",
    "L1": "低风险写入，必须先展示将写入的路径和内容摘要。",
    "L2": "中风险操作，必须展示命令、影响范围、验证方式，并等待确认。",
    "L3": "高风险操作，默认不执行；只提供人工计划，除非用户明确批准精确动作。",
}


def find_prescription(rx_id: str, text: str, prescriptions: list[Prescription]) -> Prescription | None:
    if rx_id:
        for item in prescriptions:
            if item.rx_id == rx_id:
                return item
        return None
    matches = sorted(((score_match(text, item)[0], item) for item in prescriptions), key=lambda row: row[0], reverse=True)
    if matches and matches[0][0] > 0:
        return matches[0][1]
    return None


def risk_level(risk: str) -> str:
    for level in ["L3", "L2", "L1", "L0"]:
        if level in risk:
            return level
    return "L2"


def plan_for(item: Prescription, source: str) -> dict[str, object]:
    level = risk_level(item.risk)
    return {
        "rx_id": item.rx_id,
        "risk": item.risk,
        "risk_policy": RISK_POLICY[level],
        "source": source[:1000],
        "diagnosis": item.diagnosis,
        "recommended_fix": item.prescription,
        "impact": "仅处理与该药方相关的问题；不得扩大到无关文件、凭证或用户数据。",
        "confirmation_required": level != "L0",
        "preflight": [
            "确认目标路径和当前工作区",
            "保留原始错误摘要",
            "确认没有未说明的删除、覆盖、重置动作",
        ],
        "execution": [
            item.prescription,
            "如涉及写入、安装、授权或配置修改，先展示命令或 diff 并等待用户确认。",
        ],
        "verification": [
            "重新运行触发该问题的最小命令",
            "如果失败，记录病历并降级为人工复核",
        ],
        "rollback": [
            "L0 无需回滚",
            "L1/L2 使用修改前备份或反向 diff",
            "L3 默认不执行，必须先定义回滚方案",
        ],
    }


def render_markdown(plan: dict[str, object]) -> str:
    lines = [
        "皮皮虾医生修复计划",
        "",
        f"药方：{plan['rx_id']}",
        f"风险：{plan['risk']}",
        f"是否需要确认：{'是' if plan['confirmation_required'] else '否'}",
        "",
        f"诊断：{plan['diagnosis']}",
        f"建议修复：{plan['recommended_fix']}",
        f"影响范围：{plan['impact']}",
        f"风险策略：{plan['risk_policy']}",
        "",
        "执行前检查：",
    ]
    for item in plan["preflight"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("执行步骤：")
    for item in plan["execution"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("验证方式：")
    for item in plan["verification"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("回滚方式：")
    for item in plan["rollback"]:
        lines.append(f"- {item}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a safe OpenClaw Doctor repair plan")
    parser.add_argument("--text", default="", help="error or symptom text")
    parser.add_argument("--rx-id", default="", help="explicit prescription ID")
    parser.add_argument("--prescriptions", default=str(Path(__file__).resolve().parents[1] / "references" / "prescriptions.md"))
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    prescriptions = load_prescriptions(Path(args.prescriptions))
    item = find_prescription(args.rx_id, args.text, prescriptions)
    if not item:
        print("未找到可生成修复计划的药方。请先运行 prescription_match.py。")
        return 1
    plan = plan_for(item, args.text or args.rx_id)
    if args.format == "json":
        print(json.dumps({"prescription": asdict(item), "plan": plan}, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
