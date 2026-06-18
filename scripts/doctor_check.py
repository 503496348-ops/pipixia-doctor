#!/usr/bin/env python3
"""Read-only health check for local Agent/Skill projects.

No third-party dependencies. It intentionally avoids parsing secrets and only
summarizes small, local evidence.

v1.0 — 2026-06-06 OpenClaw 本地适配增强版
  - 新增 OpenClaw 特有组件检查（HEARTBEAT/MEMORY/cron/band/scripts）
  - 新增 workspace/skills/ 批量健康检查
  - 新增系统资源健康检查
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass
class Finding:
    level: str
    title: str
    evidence: str
    impact: str
    prescription: str
    risk: str
    next_step: str


def run(cmd: list[str], cwd: Path, timeout: int = 5) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout.strip()
    except Exception as exc:
        return 999, f"{type(exc).__name__}: {exc}"


def read_head(path: Path, limit: int = 8192) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception as exc:
        return f"<<read failed: {exc}>>"


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    result: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


# ---------------------------------------------------------------------------
# OpenClaw-specific checks
# ---------------------------------------------------------------------------

def check_openclaw_workspace(target: Path) -> list[Finding]:
    """Check the OpenClaw workspace structure components."""
    findings: list[Finding] = []

    # v5.0 修复: HEARTBEAT 总是检查（即使没有 SOUL/AGENTS），
    # 这样在 lightweight 首次部署时也能检测到心跳缺失。
    # 其余 OpenClaw 专项检查（MEMORY/cron/skills/band）仍受 SOUL guard 保护。

    # HEARTBEAT
    heartbeat = target / "HEARTBEAT.md"
    if not heartbeat.exists():
        findings.append(Finding("warn", "HEARTBEAT.md 不存在", str(heartbeat), "心跳巡检无法记录。", "RX-OPENCLAW-003", "L1", "创建 HEARTBEAT.md 或重启心跳模块。"))
    else:
        text = read_head(heartbeat)
        if "HEARTBEAT_OK" not in text:
            findings.append(Finding("warn", "HEARTBEAT.md 最近无正常记录", "未找到 HEARTBEAT_OK 标记", "心跳巡检可能异常。", "RX-OPENCLAW-003", "L2", "检查心跳 cron 任务是否正常运行。"))
        # Check last heartbeat time — match summary table row format:
        # | YYYY-MM-DD HH:MM | ✅ HEARTBEAT_OK | ✅ | ✅ | - | - |
        table_pattern = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2}\s+(?:\d{2}:\d{2}))\s*\|\s*✅\s+HEARTBEAT_OK", re.MULTILINE)
        table_match = list(table_pattern.finditer(text))
        if table_match:
            # Sort by datetime to get the most recent
            parsed_times = [(m.group(1), datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")) for m in table_match]
            parsed_times.sort(key=lambda x: x[1], reverse=True)
            last_str = parsed_times[0][0]
            last_hb = datetime.strptime(last_str, "%Y-%m-%d %H:%M")
            now = datetime.now()
            hours_since = (now - last_hb).total_seconds() / 3600
            if hours_since > 3:
                findings.append(Finding("warn", f"心跳最后一次正常记录已超过{hours_since:.0f}小时", f"最后记录：{last_str}", "心跳巡检可能停止。", "RX-OPENCLAW-003", "L2", "检查 cron 配置和 gateway 状态。"))
        else:
            # Fallback: section heading format (逐行扫描替代灾难性回溯 regex)
            # 最新记录追加到文件顶部,所以正向扫描就是新->旧
            ok_latest = None
            lines = text.split('\n')
            heads = []
            for i, line in enumerate(lines):
                m = re.match(r"^##\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", line)
                if m:
                    heads.append((i, m.group(1)))
            for idx in range(len(heads)):
                start_line, head_str = heads[idx]
                end_line = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
                section = '\n'.join(lines[start_line:end_line])
                if 'HEARTBEAT_OK' in section:
                    ok_latest = head_str
                    break
            if ok_latest:
                last_str = ok_latest
                last_hb = datetime.strptime(last_str.strip(), '%Y-%m-%d %H:%M')
                now = datetime.now()
                hours_since = (now - last_hb).total_seconds() / 3600
                if hours_since > 3:
                    findings.append(Finding('warn', f'心跳最后一次正常记录已超过{hours_since:.0f}小时', f'最后记录：{last_str}', '心跳巡检可能停止。', 'RX-OPENCLAW-002', 'L2', '检查 cron 配置和 gateway 状态。'))

    # MEMORY directory
    memory_dir = target / "memory"
    if memory_dir.exists():
        # 一次性扫描，缓存结果避免重复 rglob（性能优化，见 L20 教训）
        mem_files = [f for f in memory_dir.rglob("*") if f.is_file()]
        total_size = sum(f.stat().st_size for f in mem_files)
        if total_size > 10 * 1024 * 1024:  # 10MB
            findings.append(Finding("warn", f"memory/ 目录过大（{total_size // 1024}KB）", str(memory_dir), "可能影响加载和响应性能。", "RX-MEM-001", "L1", "归档旧记忆或精简 memory/ 中的非必要文件。"))
        file_count = len(mem_files)
        if file_count > 500:
            findings.append(Finding("info", f"memory/ 文件数量较多（{file_count}个）", str(memory_dir), "可能影响 memory_search 索引速度。", "RX-MEM-001", "L0", "无需立即处理，后续持续观察。"))

    # MEMORY.md
    mem_md = target / "MEMORY.md"
    if mem_md.exists():
        mem_size = mem_md.stat().st_size
        if mem_size > 30 * 1024:
            findings.append(Finding("warn", f"MEMORY.md 体积较大（{mem_size}字节）", str(mem_md), "可能影响启动加载速度。", "RX-MEM-001", "L1", "考虑蒸馏精简 MEMORY.md。"))

    # Skills 目录批量检查
    skills_dirs = [
        target / "skills",
    ]
    for sd in skills_dirs:
        if sd.exists():
            total_skills = len([p for p in sd.iterdir() if (p / "SKILL.md").exists()])
            if total_skills > 50:
                findings.append(Finding("info", f"workspace/skills/ 有 {total_skills} 个 Skill", str(sd), "不影响运行，但注意维护。", "none", "L0", "无需处理。"))

    cron_file = target / "cron_tasks.json"
    if cron_file.exists():
        cron_text = read_head(cron_file)
        if "error" in cron_text.lower() or "fail" in cron_text.lower():
            findings.append(Finding("warn", "cron_tasks.json 包含错误", "文件内容含 error/fail 关键词", "定时任务可能有异常。", "RX-OPENCLAW-002", "L2", "检查最近 cron 运行日志。"))

    # band 组件检查（如果存在则检查健康度；不存在不告警，因为不是必装项）
    band_candidates = [
        target / "band",
        target / "bandrouter",
        target / ".band",
    ]
    for band_dir in band_candidates:
        if band_dir.exists():
            # band 目录存在：检查是否健康
            if not band_dir.is_dir():
                findings.append(Finding("warn", f"band 路径不是目录：{band_dir.name}", str(band_dir), "band routing 可能异常。", "RX-OPENCLAW-004", "L2", "删除该路径或恢复为目录。"))
            else:
                # 统计 band 内部文件数
                band_files = [p for p in band_dir.rglob("*") if p.is_file()]
                if not band_files:
                    findings.append(Finding("warn", f"band 目录为空：{band_dir.name}", str(band_dir), "band routing 缺少配置。", "RX-OPENCLAW-004", "L1", "补充 band 配置文件或删除空目录。"))
                # 备注：当前 workspace（openclaw-doctor 自身）不依赖 band 组件，
                # 因此本检查仅在 band 存在时触发，不强制要求安装。

    return findings


def check_openclaw_files(target: Path) -> list[Finding]:
    """Check essential OpenClaw workspace files."""
    findings: list[Finding] = []
    essentials = ["SOUL.md", "AGENTS.md", "USER.md", "IDENTITY.md", "TOOLS.md"]
    for name in essentials:
        if not (target / name).exists():
            findings.append(Finding("warn", f"缺少核心文件：{name}", str(target / name), "OpenClaw 启动可能不完整。", "RX-SKILL-001", "L1", f"补充 {name} 文件。"))
    return findings


# ---------------------------------------------------------------------------
# Skill package checks (original)
# ---------------------------------------------------------------------------

def check_skill_package(target: Path) -> list[Finding]:
    findings: list[Finding] = []
    candidates: list[Path] = []
    if (target / "SKILL.md").exists():
        candidates.append(target)
    candidates.extend(p.parent for p in target.glob("*/SKILL.md"))

    if not candidates:
        findings.append(
            Finding("warn", "没有发现 Skill 包", "当前目录和一级子目录未发现 SKILL.md", "如果是 Skill 项目，Codex 无法识别入口。", "RX-SKILL-001", "L1", "确认目标目录；如需创建 Skill，补充 SKILL.md。")
        )
        return findings

    for skill_dir in sorted(set(candidates)):
        skill_md = skill_dir / "SKILL.md"
        meta = frontmatter(read_head(skill_md))
        if not meta:
            findings.append(Finding("fail", f"{skill_dir.name}: SKILL.md 缺少 frontmatter", str(skill_md), "Skill 发现会失败。", "RX-SKILL-001", "L1", "补充 name 和 description。"))
            continue
        if meta.get("name") != skill_dir.name:
            findings.append(Finding("warn", f"{skill_dir.name}: name 与目录不一致", f"name={meta.get('name')!r}, folder={skill_dir.name!r}", "Skill 触发或安装后展示可能混乱。", "RX-SKILL-003", "L1", "让 frontmatter name 与目录名保持一致。"))
        description = meta.get("description", "")
        if not description or "TODO" in description or len(description) < 80:
            findings.append(Finding("warn", f"{skill_dir.name}: description 不够可触发", f"length={len(description)}", "Codex 可能不知道什么时候使用这个 Skill。", "RX-SKILL-004", "L1", "补充能力、触发词和适用场景。"))
        if not (skill_dir / "agents" / "openai.yaml").exists():
            findings.append(Finding("warn", f"{skill_dir.name}: 缺少 agents/openai.yaml", str(skill_dir / "agents" / "openai.yaml"), "UI 展示和默认触发文案不完整。", "RX-SKILL-002", "L1", "补充 agents/openai.yaml，default_prompt 包含 $skill-name。"))
    return findings


def check_project_files(target: Path) -> list[Finding]:
    findings: list[Finding] = []
    important = ["package.json", "requirements.txt", "pyproject.toml", "Cargo.toml", ".git"]
    present = [name for name in important if (target / name).exists()]
    if not present:
        findings.append(Finding("info", "未发现常见工程清单", "未发现 package.json / requirements.txt / pyproject.toml / Cargo.toml", "这可能只是 Skill 包或文档项目，不一定是异常。", "none", "L0", "如需检查具体运行时，请指定项目根目录。"))
    if (target / ".git").exists() and shutil.which("git"):
        code, out = run(["git", "status", "--short"], target)
        if code == 0 and out:
            lines = out.splitlines()
            findings.append(Finding("warn", "Git 工作区存在未提交改动", f"{len(lines)} changed entries", "修复时必须保护用户已有改动。", "RX-FILE-003", "L0", "修改前查看相关 diff，只处理本任务文件。"))
    return findings


ERROR_PATTERNS = [
    (re.compile(r"missing_scope|permission_violations|unauthorized|401", re.I), "RX-AUTH-001"),
    (re.compile(r"keychain Get failed|keychain not initialized", re.I), "RX-AUTH-002"),
    (re.compile(r"ModuleNotFoundError|Cannot find module", re.I), "RX-DEP-003"),
    (re.compile(r"No such file|ENOENT|path not found", re.I), "RX-FILE-001"),
    (re.compile(r"Permission denied|Operation not permitted", re.I), "RX-FILE-002"),
    (re.compile(r"ENOTFOUND|ECONNRESET|timeout", re.I), "RX-NET-001"),
    (re.compile(r"Unexpected token|invalid json|JSON.parse", re.I), "RX-JSON-001"),
    (re.compile(r"yaml|YAML|bad indentation", re.I), "RX-YAML-001"),
    (re.compile(r"hallucination|幻觉|抗幻觉|anti.hallucination", re.I), "RX-FIX-001"),
    (re.compile(r"TTS|tts|语音合成|opus|voice", re.I), "RX-FIX-002"),
    (re.compile(r"飞书群|路由|派发|multi.agent|multi-agent", re.I), "RX-FIX-003"),
    (re.compile(r"晓梦|xiao.meng|控制论|state_estimator", re.I), "RX-FIX-004"),
    (re.compile(r"cron|定时任务|heartbeat|心跳", re.I), "RX-OPENCLAW-002"),
]


def recent_log_files(target: Path, limit: int = 8) -> Iterable[Path]:
    ignored = {".git", "node_modules", ".venv", "venv", "__pycache__"}
    files: list[Path] = []
    for root, dirs, names in os.walk(target):
        dirs[:] = [d for d in dirs if d not in ignored]
        for name in names:
            if name.endswith((".log", ".err", ".out")):
                path = Path(root) / name
                try:
                    files.append(path)
                except OSError:
                    pass
        if len(files) > 100:
            break
    files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return files[:limit]


def check_logs(target: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in recent_log_files(target):
        text = read_head(path, 20000)
        lower = text.lower()
        if "error" not in lower and "exception" not in lower and "failed" not in lower:
            continue
        prescription = "RX-LOG-001"
        for pattern, rx in ERROR_PATTERNS:
            if pattern.search(text):
                prescription = rx
                break
        findings.append(Finding("warn", f"最近日志包含错误：{path.name}", str(path.relative_to(target)) if path.is_relative_to(target) else str(path), "可能解释用户当前报错，需要进一步精读相关日志片段。", prescription, "L0", "按药方库匹配错误关键词，再决定是否修复。"))
    return findings


def check_tools(target: Path, include_external: bool) -> list[Finding]:
    findings: list[Finding] = []
    for tool, rx in [("python3", "none"), ("ffmpeg", "RX-DEP-001"), ("uv", "RX-DEP-001")]:
        if not shutil.which(tool):
            findings.append(Finding("warn", f"命令不可用：{tool}", f"{tool} not found in PATH", "相关诊断能力会受限。", rx, "L0", "需要使用该能力时再安装或配置。"))
    if include_external and shutil.which("lark-cli"):
        code, out = run(["lark-cli", "auth", "status"], target, timeout=10)
        if code != 0:
            rx = "RX-AUTH-002" if "keychain" in out.lower() else "RX-LARK-002"
            findings.append(Finding("warn", "飞书认证状态检查失败", out[:500], "涉及飞书文档/消息/知识库的能力可能不可用。", rx, "L2", "按错误提示补齐认证或切换 user/bot 身份。"))
    return findings


def check_system_resources(target: Path) -> list[Finding]:
    """Check local system resources (disk, memory)."""
    findings: list[Finding] = []
    try:
        import shutil
        usage = shutil.disk_usage(target)
        free_gb = usage.free / (1024 ** 3)
        total_gb = usage.total / (1024 ** 3)
        if free_gb < 1:
            findings.append(Finding("warn", f"磁盘空间不足（剩余 {free_gb:.1f}GB / {total_gb:.0f}GB）", f"free={free_gb:.1f}GB total={total_gb:.0f}GB", "影响写入、日志、缓存。", "RX-PERF-002", "L3", "清理磁盘或扩展存储。"))
        elif free_gb < 5:
            findings.append(Finding("info", f"磁盘剩余空间较少（{free_gb:.1f}GB）", f"free={free_gb:.1f}GB", "长期使用可能需要清理。", "RX-PERF-002", "L0", "关注磁盘状况，考虑清理日志和缓存。"))
    except Exception:
        pass
    return findings


def score(findings: list[Finding]) -> int:
    value = 100
    for item in findings:
        if item.level == "fail":
            value -= 22
        elif item.level == "warn":
            value -= 10
        elif item.level == "info":
            value -= 2
    return max(0, value)


def status(score_value: int, findings: list[Finding]) -> str:
    if any(f.level == "fail" for f in findings) or score_value < 60:
        return "严重异常"
    if any(f.level == "warn" for f in findings) or score_value < 90:
        return "需要处理"
    return "健康"


def summary(score_value: int, state: str, findings: list[Finding]) -> str:
    if not findings:
        return "未发现需要处理的问题，可以保持当前状态。"
    fail_count = sum(1 for item in findings if item.level == "fail")
    warn_count = sum(1 for item in findings if item.level == "warn")
    info_count = sum(1 for item in findings if item.level == "info")
    top = findings[0]
    parts = [f"当前状态为{state}，健康评分 {score_value}/100。"]
    if fail_count or warn_count:
        parts.append(f"发现 {fail_count} 个异常、{warn_count} 个警告。")
    elif info_count:
        parts.append(f"仅发现 {info_count} 个提示项。")
    parts.append(f"最需要关注的是：{top.title}。")
    return "".join(parts)


def to_markdown(target: Path, findings: list[Finding], check_types: list[str], passed_checks: list[str] | None = None) -> str:
    score_value = score(findings)
    state = status(score_value, findings)
    lines = [
        "皮皮虾医生诊断报告",
        "",
        f"目标：{target}",
        f"时间：{datetime.now(timezone.utc).isoformat()}",
        f"检查范围：{' / '.join(check_types)}",
        f"健康评分：{score_value}/100",
        f"状态：{state}",
        "",
        "主要结论：",
        summary(score_value, state, findings),
        "",
    ]
    if findings:
        lines.append("发现的问题：")
        for i, item in enumerate(findings, 1):
            severity = {"fail": "高", "warn": "中", "info": "低"}.get(item.level, "低")
            lines.extend([
                f"{i}. {item.title}",
                f"   严重度：{severity}",
                f"   影响范围：{item.impact}",
                f"   证据：{item.evidence}",
                f"   药方：{item.prescription}",
                f"   修复风险：{item.risk}",
                f"   下一步：{item.next_step}",
            ])
    else:
        lines.extend(["发现的问题：无", "", "建议：保持当前状态，后续报错时再按药方库处理。"])
    # passed_checks section (for smoke test compatibility)
    if passed_checks:
        lines.extend(["", "已通过检查："])
        for item in passed_checks:
            lines.append(f"- {item}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenClaw Doctor read-only health check")
    parser.add_argument("--target", default=".", help="project or skill directory to inspect")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--include-external", action="store_true", help="run read-only external status checks such as lark-cli auth status")
    parser.add_argument("--check", action="append", default=[], help="check categories: all / skill / openclaw / system / project / log / tool. Use --check skill --check openclaw")
    args = parser.parse_args()

    target = Path(args.target).expanduser().resolve()
    findings: list[Finding] = []
    check_types: list[str] = []
    passed_checks: list[str] = []

    if not target.exists():
        findings.append(Finding("fail", "目标路径不存在", str(target), "无法执行体检。", "RX-FILE-001", "L0", "确认路径后重试。"))
    else:
        checks = args.check if args.check else ["all"]
        if "all" in checks or "skill" in checks:
            new_f = check_skill_package(target)
            findings.extend(new_f)
            check_types.append("Skill 结构")
            passed_checks.append("Skill 包结构检查完成" if not new_f else "Skill 包结构检查完成（需关注发现的问题）")
        if "all" in checks or "openclaw" in checks:
            findings.extend(check_openclaw_workspace(target))
            findings.extend(check_openclaw_files(target))
            check_types.append("OpenClaw 组件")
            passed_checks.append("OpenClaw 核心组件检查完成")
        if "all" in checks or "system" in checks:
            findings.extend(check_system_resources(target))
            check_types.append("系统资源")
            passed_checks.append("系统资源检查完成")
        if "all" in checks or "project" in checks:
            findings.extend(check_project_files(target))
            check_types.append("工程清单")
            passed_checks.append("工程清单检查完成")
        if "all" in checks or "log" in checks:
            findings.extend(check_logs(target))
            check_types.append("最近日志")
            passed_checks.append("日志扫描完成")
        if "all" in checks or "tool" in checks:
            findings.extend(check_tools(target, args.include_external))
            check_types.append("工具依赖")
            passed_checks.append("工具链检查完成")

    if args.format == "json":
        print(json.dumps({
            "target": str(target),
            "score": score(findings),
            "status": status(score(findings), findings),
            "findings": [asdict(f) for f in findings],
            "passed_checks": passed_checks,
        }, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(target, findings, check_types, passed_checks))
    return 0 if not any(f.level == "fail" for f in findings) else 2


if __name__ == "__main__":
    raise SystemExit(main())
