#!/usr/bin/env python3
"""皮皮虾医生 v5.0 脱敏脚本 - release 前必跑

Usage:
    python3 scripts/redact_release.py openclaw-doctor/ > openclaw-doctor-redacted/
    python3 scripts/redact_release.py openclaw-doctor-lightweight/ > /tmp/lw-redacted/
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# 脱敏规则（per 用户 2026-06-08 决策："脱敏除噪+打包"）
# ---------------------------------------------------------------------------
REDACT_RULES: list[tuple[re.Pattern[str], str]] = [
    # 1. 飞书 open_id（用户 + 守夜人）
    (re.compile(r"ou_xxx_PINK_USER"), "ou_xxx_PINK_USER"),
    (re.compile(r"ou_xxx_AGENT_BOT"), "ou_xxx_AGENT_BOT"),
    (re.compile(r"ou_xxx_PINK_USER"), "ou_xxx_PINK_USER"),
    # 2. 飞书 chat_id（4 个群）
    (re.compile(r"oc_xxx_EVOLUTION_GROUP"), "oc_xxx_EVOLUTION_GROUP"),
    (re.compile(r"oc_xxx_AI_EXPLORE_1"), "oc_xxx_AI_EXPLORE_1"),
    (re.compile(r"oc_xxx_AI_EXPLORE_2"), "oc_xxx_AI_EXPLORE_2"),
    (re.compile(r"oc_xxx_AI_EXPLORE_3"), "oc_xxx_AI_EXPLORE_3"),
    (re.compile(r"oc_xxx_PRIVATE_GROUP"), "oc_xxx_PRIVATE_GROUP"),
    (re.compile(r"oc_xxx_SEED_GROUP"), "oc_xxx_SEED_GROUP"),
    (re.compile(r"oc_xxx_PROJECT_4"), "oc_xxx_PROJECT_4"),
    (re.compile(r"oc_xxx_AGENT_5"), "oc_xxx_AGENT_5"),
    # 3. 飞书 app_id（守夜人 app）
    (re.compile(r"cli_xxx_APP"), "cli_xxx_APP"),
    # 4. 本地路径（用户本机）
    (re.compile(r"<HOME>/"), "<HOME>/.openclaw/"),
    (re.compile(r"<HOME>/\s]+"), "<HOME>"),
    (re.compile(r"<HOME>/\s]+"), "<HOME>"),
    # 5. 邮箱（除 examples.com / feishu.cn / 飞书域外）
    (re.compile(r"\b[A-Za-z0-9._%+-]+@(?!examples?\.)(?!feishu\.)(?!github\.com)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED:email]"),
    # 6. IP 地址
    (re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"), "[REDACTED:ip]"),
    # 7. 手机号
    (re.compile(r"(?<!\d)1[3-9][0-9]{9}(?!\d)"), "[REDACTED:phone]"),
    # 8. 用户/陈龙(团队)(团队)等真实人名 → 通用占位符
    (re.compile(r"陈龙(团队)(团队)"), "陈龙(团队)(团队)"),
    (re.compile(r"陈龙(团队)"), "陈龙(团队)(团队)"),
    (re.compile(r"团队长"), "团队长"),
    (re.compile(r"用户"), "用户"),
    (re.compile(r"团队成员"), "团队成员"),
    (re.compile(r"团队成员"), "团队成员"),
    (re.compile(r"团队成员"), "团队成员"),
    # 9. Agent 昵称
    (re.compile(r"亦菲-AGENT"), "亦菲-AGENT"),
    (re.compile(r"测试用户"), "测试用户"),
    (re.compile(r"测试用户"), "测试用户"),
    (re.compile(r"测试用户"), "测试用户"),
    (re.compile(r"测试用户"), "测试用户"),
    # 10. 用户专属场景描述（用通用示例替换）
    (re.compile(r"示例: Agent 静默时无 watchdog，sub-agent 失联导致任务半完成"),
     "示例: Agent 静默时无 watchdog，sub-agent 失联导致任务半完成"),
    (re.compile(r"示例: Agent 静默时无 watchdog，sub-agent 失联导致任务半完成"),
     "示例: Agent 静默时无 watchdog，sub-agent 失联导致任务半完成"),
    # 11. 仓库信息
    (re.compile(r"TEAM_ACCOUNT"), "TEAM_ACCOUNT"),
    # 12. 飞书 wiki 链接（用户专属）
    (re.compile(r"https://vcnvmnln7wit\.feishu\.cn/"), "https://YOUR_TENANT.feishu.cn/"),
    # 13. 飞书 doc 链接
    (re.compile(r"YOUR_DOC_ID"), "YOUR_DOC_ID"),
    (re.compile(r"YOUR_DOC_ID"), "YOUR_DOC_ID"),
    (re.compile(r"YOUR_WIKI_ID"), "YOUR_WIKI_ID"),
]

# docs/ 目录是陈龙(团队)(团队)知识库备份，**整个不打包**
EXCLUDE_DIRS = ["docs", "__pycache__", ".git", "state/health_score_state.json", "state/heartbeat_state.json", "state/pcec_state.json", "state/maintenance_state.json", "state/ten_step_state.json"]


def should_exclude(path: Path, source_root: Path) -> bool:
    """判断是否应该排除。"""
    rel = path.relative_to(source_root)
    for part in rel.parts:
        if part in {"docs", "__pycache__", ".git"}:
            return True
    rel_str = str(rel)
    for exclude in EXCLUDE_DIRS:
        if rel_str.startswith(exclude):
            return True
    return False


def redact_text(text: str) -> str:
    """对单段文本应用所有脱敏规则。"""
    for pattern, replacement in REDACT_RULES:
        text = pattern.sub(replacement, text)
    return text


def process_file(src: Path, dst: Path, source_root: Path) -> None:
    """处理单个文件：脱敏内容，保留非文本文件。"""
    dst.parent.mkdir(parents=True, exist_ok=True)

    # 文本文件：脱敏
    if src.suffix in {".md", ".py", ".sh", ".yaml", ".txt", ".json", ".log", ".jsonl"}:
        try:
            content = src.read_text(encoding="utf-8", errors="replace")
            redacted = redact_text(content)
            dst.write_text(redacted, encoding="utf-8")
        except Exception as exc:
            print(f"  WARN: {src.relative_to(source_root)} 读取失败: {exc}")
    else:
        # 二进制文件：原样复制
        shutil.copy2(src, dst)


def main() -> int:
    parser = argparse.ArgumentParser(description="皮皮虾医生 v5.0 脱敏工具")
    parser.add_argument("source", help="源目录（如 openclaw-doctor/）")
    parser.add_argument("--output", "-o", help="输出目录（默认同源目录加 -redacted 后缀）")
    parser.add_argument("--dry-run", action="store_true", help="只扫描不输出")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    if not source.is_dir():
        print(f"❌ 源目录不存在：{source}")
        return 1

    output = Path(args.output).resolve() if args.output else source.parent / f"{source.name}-redacted"
    if output.exists() and not args.dry_run:
        shutil.rmtree(output)

    if args.dry_run:
        # 只扫描
        file_count = 0
        match_count = 0
        for src in source.rglob("*"):
            if not src.is_file() or should_exclude(src, source):
                continue
            if src.suffix in {".md", ".py", ".sh", ".yaml", ".txt", ".json", ".log", ".jsonl"}:
                content = src.read_text(encoding="utf-8", errors="replace")
                for pattern, _ in REDACT_RULES:
                    if pattern.search(content):
                        rel = src.relative_to(source)
                        print(f"  HIT: {rel}")
                        match_count += 1
                        break
                file_count += 1
        print(f"\n扫描完成: {file_count} 个文本文件, {match_count} 个含敏感信息")
        return 0

    # 实际脱敏
    output.mkdir(parents=True, exist_ok=True)
    file_count = 0
    for src in source.rglob("*"):
        if not src.is_file():
            continue
        if should_exclude(src, source):
            continue
        rel = src.relative_to(source)
        dst = output / rel
        process_file(src, dst, source)
        file_count += 1

    print(f"✅ 脱敏完成: {output}")
    print(f"   复制了 {file_count} 个文件（排除 docs/ + __pycache__/）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
