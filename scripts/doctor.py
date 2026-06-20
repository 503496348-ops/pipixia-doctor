#!/usr/bin/env python3
"""
皮皮虾医生（OpenClaw Doctor）v5.0 — 统一 CLI 入口

合并自:
  - openclaw-doctor v4.0 (本地多脚本)
  - hermes-doctor v0.1.1 (Hermes 统一 CLI 框架)

结构: 统一 CLI (doctor.py) + 15 个专用脚本 + bailongma-doctor 包装器
使用方法:
  python3 doctor.py check --target . --format markdown
  python3 doctor.py match --text "fetch failed timeout"
  python3 doctor.py plan --text "unknown tool"
  python3 doctor.py record --title "问题" --status fixed --summary "怎么了"
  python3 doctor.py search --query "关键词"
  python3 doctor.py route --text "皮皮虾医生 体检"
  python3 doctor.py validate --target .
  python3 doctor.py test --target .
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCORING_FORMULA = "Health Score = max(0, 100 - fail_count × 22 - warn_count × 10 - info_count × 2)"
MIN_PRESCRIPTIONS = 12

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    level: str  # fail | warn | info
    title: str
    evidence: str
    impact: str
    prescription: str
    risk: str  # L0-L3
    next_step: str


@dataclass
class Prescription:
    rx_id: str
    symptoms: str
    diagnosis: str
    prescription: str
    risk: str


@dataclass
class Route:
    intent: str
    action: str
    command: list[str]
    confirmation_required: bool
    reply_hint: str


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def read_text(path: Path, limit: int = 200000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception as exc:
        return f"<<read failed: {exc}>>"


def split_markdown_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    cells: list[str] = []
    current: list[str] = []
    in_code = False
    escaped = False
    for char in text:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            current.append(char)
            escaped = True
            continue
        if char == "`":
            in_code = not in_code
            current.append(char)
            continue
        if char == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    cells.append("".join(current).strip())
    return cells


def tokens(text: str) -> list[str]:
    raw = re.findall(r"`([^`]+)`|([A-Za-z0-9_:/.-]{3,})|([\u4e00-\u9fff]{2,})", text)
    result: list[str] = []
    for quoted, bare, chinese in raw:
        value = (quoted or bare or chinese).strip().lower()
        if value and value not in {"and", "the", "with", "none", "not", "fail", "failed", "error", "missing", "invalid"}:
            result.append(value)
    return result


def redacted(value: str) -> str:
    result = value
    result = re.sub(
        r"(?i)(token|cookie|password|passwd|secret|api[_-]?key)\s*[:=]\s*['\"]?[^'\"\s]+",
        lambda match: f"{match.group(1)}=[REDACTED]",
        result,
        flags=re.S,
    )
    result = re.sub(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        "[REDACTED_PRIVATE_KEY]",
        result,
        flags=re.S,
    )
    return result


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# Prescription loading & matching
# ---------------------------------------------------------------------------


def load_prescriptions(path: Path | None = None) -> list[Prescription]:
    path = path or ROOT / "references" / "prescriptions.md"
    rows: list[Prescription] = []
    for line in read_text(path, 200000).splitlines():
        if not line.startswith("| RX-"):
            continue
        cells = split_markdown_row(line)
        if len(cells) != 5:
            continue
        rows.append(Prescription(*cells))
    return rows


def score_match(query: str, item: Prescription) -> tuple[int, list[str]]:
    haystack = f"{item.rx_id} {item.symptoms} {item.diagnosis} {item.prescription}".lower()
    query_l = query.lower()
    query_tokens = set(tokens(query))
    matched: list[str] = []
    score = 0
    if item.rx_id.lower() in query_l:
        score += 100
        matched.append(item.rx_id)
    for token in tokens(item.symptoms):
        if token in query_l or token in query_tokens:
            score += 22 if len(token) > 6 else 12
            matched.append(token)
    for token in query_tokens:
        if token in haystack:
            score += 4
    return score, sorted(set(matched))


def match_prescriptions(query: str, prescriptions: list[Prescription]) -> list[tuple[int, list[str], Prescription]]:
    matches = sorted(
        ((score_match(query, item)[0], score_match(query, item)[1], item) for item in prescriptions),
        key=lambda row: row[0],
        reverse=True,
    )
    matches = [row for row in matches if row[0] >= 8]
    if matches:
        threshold = max(8, int(matches[0][0] * 0.35))
        matches = [row for row in matches if row[0] >= threshold]
    return matches


# ---------------------------------------------------------------------------
# OpenClaw-specific checks
# ---------------------------------------------------------------------------


def collect_files(target: Path, limit: int = 500) -> list[Path]:
    ignored = {".git", "node_modules", ".venv", "venv", "__pycache__", ".doctor", ".pytest_cache"}
    files: list[Path] = []
    for root, dirs, names in os.walk(target):
        dirs[:] = [d for d in dirs if d not in ignored]
        for name in names:
            files.append(Path(root) / name)
            if len(files) >= limit:
                return files
    return files


def check_openclaw_environment(target: Path) -> tuple[list[Finding], list[str]]:
    """Check the target as an OpenClaw workspace/project."""
    findings: list[Finding] = []
    passed: list[str] = []

    files = collect_files(target)
    names = [rel(path, target) for path in files]
    lower_names = [name.lower() for name in names]

    # --- Hermes plugin manifest (if present) ---
    manifest = target / ".hermes-skill" / "plugin.json"
    marketplace = target / ".hermes-skill" / "marketplace.json"
    if manifest.exists():
        try:
            data = json.loads(read_text(manifest))
            if data.get("name"):
                passed.append(f"Hermes plugin manifest 可读取：{data.get('name')}")
            else:
                findings.append(Finding("warn", "plugin.json 缺少 name", rel(manifest, target), "Hermes 安装可能失败。", "RX-HERMES-001", "L1", "补齐 name/version/description。"))
        except json.JSONDecodeError as exc:
            findings.append(Finding("fail", "plugin.json 不是合法 JSON", f"{rel(manifest, target)}: {exc}", "Hermes 插件无法被识别。", "RX-HERMES-002", "L1", "修复 JSON 格式后重新 validate。"))
    else:
        passed.append("非 Hermes 项目（无 plugin.json），跳过 Hermes 检查")

    if marketplace.exists():
        passed.append("Hermes marketplace.json 存在")
    else:
        passed.append("非 Hermes 市场项目（无 marketplace.json）")

    # --- Essential OpenClaw files ---
    essentials = ["SOUL.md", "AGENTS.md", "IDENTITY.md", "USER.md", "TOOLS.md"]
    for name in essentials:
        if (target / name).exists():
            passed.append(f"核心文件存在：{name}")
        else:
            findings.append(Finding("warn", f"缺少核心文件：{name}", str(target / name), "OpenClaw 启动可能不完整。", "RX-OPENCLAW-001", "L1", f"补充 {name} 文件。"))

    # --- HEARTBEAT ---
    heartbeat_path = target / "HEARTBEAT.md"
    if heartbeat_path.exists():
        text = read_text(heartbeat_path, 100000)
        if "HEARTBEAT_OK" in text:
            passed.append("HEARTBEAT.md 正常（含 HEARTBEAT_OK 标记）")
        else:
            findings.append(Finding("warn", "HEARTBEAT.md 未找到 HEARTBEAT_OK 标记", str(heartbeat_path), "心跳状态可能异常。", "RX-HEARTBEAT-001", "L2", "检查心跳 cron 配置。"))
        # Check file size
        hb_size = heartbeat_path.stat().st_size
        if hb_size > 100000:
            findings.append(Finding("info", f"HEARTBEAT.md 体积较大（{hb_size // 1024}KB）", str(heartbeat_path), "可能影响读取性能。", "RX-MEM-001", "L1", "考虑归档超过30天的历史记录。"))
    else:
        findings.append(Finding("warn", "HEARTBEAT.md 不存在", "", "心跳巡检无法记录。", "RX-HEARTBEAT-002", "L1", "创建 HEARTBEAT.md。"))

    # --- MEMORY ---
    memory_dir = target / "memory"
    if memory_dir.exists():
        mem_files = [f for f in memory_dir.rglob("*") if f.is_file()]
        total_size = sum(f.stat().st_size for f in mem_files)
        file_count = len(mem_files)
        passed.append(f"memory/ 目录存在，{file_count}个文件，{total_size // 1024}KB")
        if total_size > 10 * 1024 * 1024:
            findings.append(Finding("warn", f"memory/ 过大（{total_size // 1024}KB）", str(memory_dir), "影响加载性能。", "RX-MEM-001", "L1", "归档旧记忆。"))
        # Check for heartbeat subdirectory
        hb_mem_dir = memory_dir / "heartbeat"
        if hb_mem_dir.exists():
            hb_files = list(hb_mem_dir.rglob("*"))
            hb_count = len([f for f in hb_files if f.is_file()])
            if hb_count > 80:
                findings.append(Finding("warn", f"memory/heartbeat/ 有 {hb_count} 个文件（超过阈值80）", str(hb_mem_dir), "持续WARN多轮，需清理。", "RX-MEM-002", "L1", "清理超过30天的历史心跳记录。"))

    if (target / "MEMORY.md").exists():
        mem_size = (target / "MEMORY.md").stat().st_size
        if mem_size > 30000:
            findings.append(Finding("info", f"MEMORY.md 体积 {mem_size} 字节", "", "考虑精简。", "RX-MEM-001", "L0", "蒸馏精简。"))

    # --- Skills ---
    skills_dir = target / "skills"
    if skills_dir.exists():
        skill_count = len([p for p in skills_dir.iterdir() if (p / "SKILL.md").exists()])
        passed.append(f"workspace/skills/ 目录存在，{skill_count}个Skill")
        # Check each skill for completeness
        for skill_dir in sorted(skills_dir.iterdir()):
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            text = read_text(skill_md, 5000)
            # Check for description trigger words
            desc_match = re.search(r'description[:\s]+"(.+?)"', text)
            if desc_match and len(desc_match.group(1)) < 50:
                findings.append(Finding("info", f"{skill_dir.name}: description 较短（{len(desc_match.group(1))}字符）", desc_match.group(1)[:80], "Agent 可能不清晰何时触发。", "RX-SKILL-004", "L0", "可补充触发词。"))
            if not (skill_dir / "agents" / "openai.yaml").exists():
                findings.append(Finding("info", f"{skill_dir.name}: 缺少 agents/openai.yaml", str(skill_dir / "agents"), "UI 触发文案不完整。", "RX-SKILL-002", "L0", "建议补充。"))

    # --- System resource hints ---
    load_avg = os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0)
    if max(load_avg) > 8:
        findings.append(Finding("warn", f"系统负载偏高（{max(load_avg):.2f}）", "", "可能影响响应速度。", "RX-SYS-001", "L2", "检查后台进程。"))
    else:
        passed.append(f"系统负载正常（{max(load_avg):.2f}）")

    # --- Git status ---
    try:
        proc = subprocess.run(["git", "status", "--short"], cwd=str(target), text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5)
        if proc.returncode == 0:
            changes = len([l for l in proc.stdout.splitlines() if l.strip()])
            if changes > 0:
                findings.append(Finding("info", f"Git 工作区有 {changes} 个未提交改动", "", "修改前注意保护已有改动。", "RX-FILE-003", "L0", "查看相关 diff 后处理。"))
            else:
                passed.append("Git 工作区干净")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        passed.append("Git 不可用或超时，跳过 Git 检查")

    # --- Log files scan ---
    logs = [path for path in files if path.suffix in {".log", ".err", ".out"}]
    log_findings = 0
    for path in sorted(logs, key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:8]:
        text = read_text(path, 50000)
        lower = text.lower()
        if not any(word in lower for word in ["error", "failed", "exception", "timeout", "失败", "异常"]):
            continue
        rx_id = "RX-LOG-001"
        title = "最近日志包含错误"
        if re.search(r"fetch failed|failed to fetch|访问不到|取不到|timeout", text, re.I):
            rx_id, title = "RX-RUNTIME-001", "网页数据获取失败"
        elif re.search(r"unknown tool|tool .*not found|工具不存在|工具调用失败", text, re.I):
            rx_id, title = "RX-TOOL-001", "工具调用失败"
        elif re.search(r"captcha|rate limit|login required|验证码|请求太频繁|登录", text, re.I):
            rx_id, title = "RX-SAFETY-002", "平台限制或登录态问题"
        findings.append(Finding("warn", f"{title}：{path.name}", rel(path, target), "可能影响诊断。", rx_id, "L0", "先匹配药方。"))
        log_findings += 1
    if not logs:
        passed.append("未发现 .log/.err/.out 日志文件")
    elif log_findings == 0:
        passed.append(f"扫描 {min(len(logs), 8)} 个日志文件，未发现错误")

    # --- Tool availability ---
    for tool in ["python3"]:
        if shutil.which(tool):
            passed.append(f"命令可用：{tool}")
        else:
            findings.append(Finding("warn", f"命令不可用：{tool}", "", "诊断能力受限。", "RX-DEP-001", "L2", "安装后再诊断。"))

    return findings, passed


# ---------------------------------------------------------------------------
# Scoring & rendering
# ---------------------------------------------------------------------------


def health_score(findings: list[Finding]) -> int:
    value = 100
    for item in findings:
        if item.level == "fail":
            value -= 22
        elif item.level == "warn":
            value -= 10
        elif item.level == "info":
            value -= 2
    return max(0, value)


def health_status(score: int, findings: list[Finding]) -> str:
    if any(item.level == "fail" for item in findings) or score < 60:
        return "严重异常"
    if any(item.level == "warn" for item in findings) or score < 90:
        return "需要处理"
    return "健康"


def severity_counts(findings: list[Finding]) -> dict[str, int]:
    return {
        "fail": sum(1 for item in findings if item.level == "fail"),
        "warn": sum(1 for item in findings if item.level == "warn"),
        "info": sum(1 for item in findings if item.level == "info"),
    }


def baseline_status(score: int, baseline_file: Path | None = None) -> dict[str, object]:
    if baseline_file is None:
        return {"status": "not_configured", "sample_count": 0, "baseline_score": None, "delta": None, "action": "首次或未配置基线时，只展示当前分数，不触发熔断。"}
    if not baseline_file.exists():
        return {"status": "not_initialized", "sample_count": 0, "baseline_score": None, "delta": None, "action": "首次运行可将当前分数作为初始参考；只读体检不会自动写入基线。"}
    try:
        data = json.loads(read_text(baseline_file, 100000))
        samples = [int(item["score"]) for item in data.get("samples", []) if "score" in item]
    except Exception:
        return {"status": "invalid", "sample_count": 0, "baseline_score": None, "delta": None, "action": "基线文件不可解析。"}
    recent = samples[-10:]
    if not recent:
        return {"status": "not_initialized", "sample_count": 0, "baseline_score": None, "delta": None, "action": "基线文件没有样本。"}
    baseline = round(sum(recent) / len(recent), 2)
    delta = round(score - baseline, 2)
    if len(recent) < 3:
        status, action = "warming_up", "样本少于3次，只提示不熔断。"
    elif len(recent) < 10:
        status, action = "partial", "样本少于10次，可提示风险。"
    elif delta <= -15:
        status, action = "downgrade", "低于基线15分以上，降级。"
    elif delta >= 10:
        status, action = "positive", "高于基线10分以上，正反馈。"
    else:
        status, action = "normal", "在基线波动范围内。"
    return {"status": status, "sample_count": len(recent), "baseline_score": baseline, "delta": delta, "action": action}


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def render_check(target: Path, findings: list[Finding], passed: list[str], baseline: dict | None = None) -> str:
    score = health_score(findings)
    state = health_status(score, findings)
    counts = severity_counts(findings)
    bsl = baseline or baseline_status(score)
    lines = [
        "🦐 皮皮虾医生（OpenClaw Doctor）诊断报告",
        "",
        f"目标：{target}",
        f"时间：{datetime.now(timezone.utc).isoformat()}",
        f"健康评分：{score}/100",
        f"状态：{state}",
        f"评分公式：{SCORING_FORMULA}",
        f"计数：fail={counts['fail']}，warn={counts['warn']}，info={counts['info']}",
        f"基线状态：{bsl['status']}；{bsl['action']}",
        "",
        "主要结论：",
    ]
    if findings:
        lines.append(f"发现 {len(findings)} 个问题。最需要关注：{findings[0].title}。")
    else:
        lines.append("未发现需要处理的问题。")
    lines.extend(["", "发现的问题："])
    if findings:
        for idx, item in enumerate(findings, 1):
            sev_map = {"fail": "高", "warn": "中", "info": "低"}
            lines.extend([
                f"{idx}. {item.title}",
                f"   严重度：{sev_map.get(item.level, '低')}",
                f"   影响范围：{item.impact}",
                f"   证据：{item.evidence}",
                f"   药方：{item.prescription}",
                f"   修复风险：{item.risk}",
                f"   下一步：{item.next_step}",
            ])
    else:
        lines.append("无")
    if passed:
        lines.extend(["", "已通过检查："])
        for item in passed:
            lines.append(f"- {item}")
    return "\n".join(lines)


def render_matches(query: str, matches: list[tuple[int, list[str], Prescription]]) -> str:
    if not matches:
        return "\n".join([
            "🦐 皮皮虾医生药方匹配",
            "",
            "未找到明确药方。",
            "",
            "下一步：先运行只读体检，摘取最关键的 20 行错误日志，再生成兜底诊断报告。",
            f"输入摘要：{query[:500]}",
        ])
    lines = ["🦐 皮皮虾医生药方匹配", ""]
    for rank, (score, matched, item) in enumerate(matches[:3], 1):
        lines.extend([
            f"{rank}. 药方：{item.rx_id}",
            f"   匹配分：{score}",
            f"   命中症状：{', '.join(matched) if matched else '弱匹配'}",
            f"   小白解释：{item.diagnosis}",
            f"   修复步骤：{item.prescription}",
            f"   风险等级：{item.risk}",
            "",
        ])
    lines.append("下一步：按最高匹配药方处理；涉及写入、安装、授权、重启或删除时先确认。")
    return "\n".join(lines)


RISK_POLICY = {
    "L0": "可自动执行，只读检查或报告生成。",
    "L1": "低风险写入，必须展示路径和内容摘要。",
    "L2": "中风险操作，必须展示命令、影响范围、验证方式，并等待确认。",
    "L3": "高风险操作，默认不执行；只提供人工计划。",
}


def risk_level(risk: str) -> str:
    for level in ["L3", "L2", "L1", "L0"]:
        if level in risk:
            return level
    return "L2"


def build_plan(item: Prescription, source: str) -> dict[str, object]:
    level = risk_level(item.risk)
    return {
        "rx_id": item.rx_id,
        "risk": item.risk,
        "risk_policy": RISK_POLICY[level],
        "source": source[:1000],
        "diagnosis": item.diagnosis,
        "recommended_fix": item.prescription,
        "impact": "仅处理目标项目相关问题，不扩大到无关文件、凭证或用户数据。",
        "confirmation_required": level != "L0",
        "preflight": [
            "确认目标路径和当前工作区",
            "保留原始错误摘要",
            "确认没有未说明的删除、覆盖、重置、读取密钥动作",
        ],
        "execution": [
            item.prescription,
            "如涉及写入、安装、授权、重启或配置修改，先展示命令或 diff 并等待用户确认。",
        ],
        "verification": [
            "重新运行触发问题的最小命令",
            "重新运行 doctor.py check 或对应子能力测试",
            "如果失败，记录病历并降级为人工复核",
        ],
        "rollback": [
            "L0 无需回滚",
            "L1/L2 使用修改前备份或反向 diff",
            "L3 默认不执行，必须先定义回滚方案",
        ],
    }


def render_plan(plan: dict[str, object]) -> str:
    lines = [
        "🦐 皮皮虾医生修复计划",
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
    lines.extend(["", "执行步骤："])
    for item in plan["execution"]:
        lines.append(f"- {item}")
    lines.extend(["", "验证方式："])
    for item in plan["verification"]:
        lines.append(f"- {item}")
    lines.extend(["", "回滚方式："])
    for item in plan["rollback"]:
        lines.append(f"- {item}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def command_check(args: argparse.Namespace) -> int:
    target = Path(args.target).expanduser().resolve()
    if not target.exists():
        findings = [Finding("fail", "目标路径不存在", str(target), "无法执行体检。", "RX-FILE-001", "L0", "确认路径后重试。")]
        passed: list[str] = []
    else:
        findings, passed = check_openclaw_environment(target)
    score = health_score(findings)
    baseline_file = Path(args.baseline_file).expanduser().resolve() if args.baseline_file else None
    bsl = baseline_status(score, baseline_file)
    if args.format == "json":
        print(json.dumps({"target": str(target), "score": score, "status": health_status(score, findings), "scoring_formula": SCORING_FORMULA, "severity_counts": severity_counts(findings), "baseline": bsl, "findings": [asdict(item) for item in findings], "passed_checks": passed}, ensure_ascii=False, indent=2))
    else:
        print(render_check(target, findings, passed, bsl))
    return 0 if not any(item.level == "fail" for item in findings) else 2


def command_match(args: argparse.Namespace) -> int:
    query = args.text
    if args.file:
        query = read_text(Path(args.file), 100000)
    matches = match_prescriptions(query, load_prescriptions())
    if args.format == "json":
        print(json.dumps({"query": query[:1000], "matches": [{"score": s, "matched": m, **asdict(p)} for s, m, p in matches[:5]]}, ensure_ascii=False, indent=2))
    else:
        print(render_matches(query, matches))
    return 0


def command_plan(args: argparse.Namespace) -> int:
    prescriptions = load_prescriptions()
    item: Prescription | None = None
    if args.rx_id:
        item = next((p for p in prescriptions if p.rx_id == args.rx_id), None)
    else:
        matches = match_prescriptions(args.text, prescriptions)
        item = matches[0][2] if matches else None
    if not item:
        print("未找到可生成修复计划的药方。请先运行 match。")
        return 1
    plan = build_plan(item, args.text or args.rx_id)
    if args.format == "json":
        print(json.dumps({"prescription": asdict(item), "plan": plan}, ensure_ascii=False, indent=2))
    else:
        print(render_plan(plan))
    return 0


def command_record(args: argparse.Namespace) -> int:
    case_dir = Path(args.case_dir).expanduser()
    case_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", redacted(args.title).strip().lower()).strip("-") or "case"
    path = case_dir / f"{timestamp}-{slug}.md"
    body = "\n".join([
        "---",
        f"title: {redacted(args.title)}",
        f"status: {args.status}",
        f"created_at: {datetime.now(timezone.utc).isoformat()}",
        "---",
        "",
        "# 皮皮虾医生病历",
        "",
        f"## Summary\n\n{redacted(args.summary)}",
    ])
    path.write_text(body + "\n", encoding="utf-8")
    print(str(path))
    return 0


def command_search(args: argparse.Namespace) -> int:
    case_dir = Path(args.case_dir).expanduser()
    query = args.query.lower()
    if not case_dir.exists():
        print("🦐 皮皮虾医生病历查询\n\n暂无病历。")
        return 0
    matches = []
    for path in sorted(case_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        text = read_text(path, 20000)
        if not query or query in text.lower() or query in path.name.lower():
            matches.append((path, text))
        if len(matches) >= 5:
            break
    lines = ["🦐 皮皮虾医生病历查询", "", f"查询词：{args.query or '(最近病历)'}", ""]
    if not matches:
        lines.append("没有找到匹配病历。")
    for path, text in matches:
        first = next((line for line in text.splitlines() if line and not line.startswith("---")), path.name)
        lines.extend([f"- {path.name}", f"  摘要：{first[:160]}"])
    print("\n".join(lines))
    return 0


def command_route(args: argparse.Namespace) -> int:
    text = args.text.strip()
    for prefix in ["白龙马医生", "皮皮虾医生", "@白龙马医生", "OpenClaw Doctor", "openclaw doctor", "@皮皮虾医生"]:
        if text.startswith(prefix):
            text = text[len(prefix):].strip(" ：:")
            break
    route: Route
    if any(word in text for word in ["体检", "看看状态", "health", "check"]):
        route = Route("health_check", "run_health_check", ["python3", "scripts/doctor.py", "check", "--target", "."], False, "返回皮皮虾医生健康报告。")
    elif any(word in text for word in ["上次", "病历", "历史", "search"]):
        query = text.split("：", 1)[-1] if "：" in text else text
        route = Route("case_search", "search_cases", ["python3", "scripts/doctor.py", "search", "--query", query], False, "返回匹配病历。")
    elif any(word in text for word in ["帮我修", "修一下", "自愈", "repair"]):
        symptom = text.split("：", 1)[-1] if "：" in text else text
        route = Route("repair_plan", "generate_repair_plan", ["python3", "scripts/doctor.py", "plan", "--text", symptom], True, "先返回修复计划，等待用户确认。")
    elif any(word in text for word in ["报错", "出错", "failed", "error", "异常", "match"]):
        symptom = text.split("：", 1)[-1] if "：" in text else text
        route = Route("prescription_match", "match_prescription", ["python3", "scripts/doctor.py", "match", "--text", symptom], False, "返回药方卡。")
    else:
        route = Route("fallback", "fallback_health_check", ["python3", "scripts/doctor.py", "check", "--target", "."], False, "未识别明确意图，先做只读体检。")
    if args.format == "json":
        print(json.dumps(asdict(route), ensure_ascii=False, indent=2))
    else:
        print("\n".join(["🦐 皮皮虾医生消息路由", "", f"意图：{route.intent}", f"动作：{route.action}", f"命令：{' '.join(route.command)}", f"是否需要确认：{'是' if route.confirmation_required else '否'}", f"回复提示：{route.reply_hint}"]))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    target = Path(args.target).expanduser().resolve()
    required = [
        "SKILL.md",
        "README.md",
        "scripts/doctor.py",
        "references/prescriptions.md",
        "references/safety_policy.md",
        "references/test_cases.md",
        "skills/hermes-check/SKILL.md",
        "skills/prescription-match/SKILL.md",
        "skills/repair-plan/SKILL.md",
        "skills/case-record/SKILL.md",
        "skills/case-search/SKILL.md",
        "skills/feishu-route/SKILL.md",
    ]
    missing = [item for item in required if not (target / item).exists()]
    if missing:
        print("FAIL missing required files:")
        for item in missing:
            print(f"- {item}")
        return 1
    # Check prescriptions
    prescriptions = load_prescriptions(target / "references" / "prescriptions.md")
    if len(prescriptions) < MIN_PRESCRIPTIONS:
        print(f"FAIL prescriptions < {MIN_PRESCRIPTIONS}: {len(prescriptions)}")
        return 1
    print("OK")
    return 0


def command_test(args: argparse.Namespace) -> int:
    root = Path(args.target).expanduser().resolve()
    py = sys.executable
    case_dir = Path(tempfile.mkdtemp(prefix="doctor-tests-"))
    script = str(root / "scripts" / "doctor.py")
    cases = [
        ("validate", [py, script, "validate", "--target", str(root)], "OK", (0,)),
        ("check", [py, script, "check", "--target", str(root)], "皮皮虾医生", (0, 2)),
        ("check-json", [py, script, "check", "--target", str(root), "--format", "json"], '"passed_checks"', (0, 2)),
        ("missing-path", [py, script, "check", "--target", "/no/such/path"], "RX-FILE-001", (2,)),
        ("rx-fetch", [py, script, "match", "--text", "fetch failed timeout 访问不到网页"], "RX-RUNTIME-001", (0,)),
        ("rx-tool", [py, script, "match", "--text", "unknown tool 工具调用失败"], "RX-TOOL-001", (0,)),
        ("rx-secret", [py, script, "match", "--text", "token=abc123 cookie=xyz password=hello"], "RX-SAFETY-001", (0,)),
        ("plan", [py, script, "plan", "--text", "login required captcha rate limit"], "是否需要确认：是", (0,)),
        ("record", [py, script, "record", "--case-dir", str(case_dir), "--title", "fetch failed", "--status", "partial", "--summary", "token=abc123"], str(case_dir), (0,)),
        ("search", [py, script, "search", "--case-dir", str(case_dir), "--query", "fetch"], "fetch", (0,)),
        ("route", [py, script, "route", "--text", "皮皮虾医生 帮我修一下：fetch failed", "--format", "json"], '"confirmation_required": true', (0,)),
    ]
    failures = 0
    for name, command, expect, codes in cases:
        ok, output = run_subprocess(command, root.parent, expect, codes)
        print(f"{'OK' if ok else 'FAIL'} {name}")
        if not ok:
            failures += 1
            print(output[:1200])
    import shutil
    shutil.rmtree(case_dir, ignore_errors=True)
    print(f"summary: {len(cases) - failures}/{len(cases)} passed")
    return 1 if failures else 0


def run_subprocess(command: list[str], cwd: Path, expect: str, exit_codes: tuple[int, ...] = (0,)) -> tuple[bool, str]:
    """Run a subprocess and check output."""
    proc = subprocess.run(command, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
    output = proc.stdout.strip()
    return proc.returncode in exit_codes and expect in output, output


# ---------------------------------------------------------------------------
# Snapshot command (v5.1 数字遗产+复活)
# ---------------------------------------------------------------------------


def command_snapshot(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(ROOT / "scripts"))
    from agent_snapshot import (
        save_snapshot, list_snapshots, diff_snapshots, restore_snapshot,
        verify_snapshot, load_manifest, render_manifest, render_diff, render_list,
    )
    target = Path(args.target).expanduser().resolve()
    snap_dir = target / ".doctor" / "snapshots"

    if args.snapshot_action == "save":
        archive = save_snapshot(target, args.description or "")
        manifest_path = archive.parent / f"{archive.stem.replace('.tar', '')}.json"
        if args.format == "json":
            manifest = load_manifest(manifest_path)
            print(json.dumps(asdict(manifest), ensure_ascii=False, indent=2))
        else:
            manifest = load_manifest(manifest_path)
            print(f"🦐 皮皮虾医生 Agent 快照已创建\n\n快照 ID：{manifest.snapshot_id}\n文件数：{manifest.total_files}\n总大小：{manifest.total_size // 1024}KB\n归档路径：{archive}")
        return 0

    elif args.snapshot_action == "list":
        snapshots = list_snapshots(target)
        if args.format == "json":
            print(json.dumps(snapshots, ensure_ascii=False, indent=2))
        else:
            print(render_list(snapshots))
        return 0

    elif args.snapshot_action == "diff":
        old_path = snap_dir / f"{args.snapshot_id}.json"
        new_path = snap_dir / f"{args.other_snapshot_id}.json"
        if not old_path.exists() or not new_path.exists():
            print("ERROR: One or both snapshot manifests not found")
            return 1
        diff = diff_snapshots(load_manifest(old_path), load_manifest(new_path))
        if args.format == "json":
            print(json.dumps(asdict(diff), ensure_ascii=False, indent=2))
        else:
            print(render_diff(diff))
        return 0

    elif args.snapshot_action == "restore":
        result = restore_snapshot(target, args.snapshot_id, dry_run=args.dry_run)
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            status = "预演" if result.get("dry_run") else ("成功" if result.get("success") else "失败")
            print(f"🦐 快照恢复{status}：{result.get('snapshot_id', '?')}，恢复 {result.get('restored_files', 0)} 个文件")
        return 0 if result.get("success") or result.get("dry_run") else 1

    elif args.snapshot_action == "verify":
        result = verify_snapshot(target, args.snapshot_id)
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            match = "一致 ✅" if result.get("matches") else "不一致 ❌"
            print(f"🦐 快照验证：{result.get('snapshot_id', '?')} 状态{match}")
        return 0 if result.get("matches") else 2

    return 0


# ---------------------------------------------------------------------------
# Learn command (v5.1 药方自学习)
# ---------------------------------------------------------------------------


def command_learn(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(ROOT / "scripts"))
    from rx_learner import (
        record_feedback, append_feedback, compute_effectiveness,
        cluster_unmatched_errors, generate_from_resolved_cases,
        analyze_gaps, render_effectiveness, render_candidates,
        render_gaps, render_report,
    )
    from dataclasses import asdict as dc_asdict
    target = Path(args.target).expanduser().resolve()

    if args.learn_action == "feedback":
        if not args.rx_id or not args.query:
            print("ERROR: --rx-id and --query are required for feedback")
            return 1
        entry = record_feedback(
            rx_id=args.rx_id, query_text=args.query, match_score=args.score,
            outcome=args.outcome, resolved=args.resolved,
            resolution_notes=args.resolution, case_id=args.case_id,
        )
        append_feedback(target, entry)
        if args.format == "json":
            print(json.dumps(entry, ensure_ascii=False, indent=2))
        else:
            print(f"🦐 反馈已记录：{args.rx_id} → {args.outcome}")
        return 0

    elif args.learn_action == "effectiveness":
        scores = compute_effectiveness(target)
        if args.format == "json":
            print(json.dumps([dc_asdict(s) for s in scores], ensure_ascii=False, indent=2))
        else:
            print(render_effectiveness(scores))
        return 0

    elif args.learn_action == "candidates":
        all_cands = cluster_unmatched_errors(target) + generate_from_resolved_cases(target)
        if args.format == "json":
            print(json.dumps([dc_asdict(c) for c in all_cands], ensure_ascii=False, indent=2))
        else:
            print(render_candidates(all_cands))
        return 0

    elif args.learn_action == "gaps":
        gaps = analyze_gaps(target)
        if args.format == "json":
            print(json.dumps(gaps, ensure_ascii=False, indent=2))
        else:
            print(render_gaps(gaps))
        return 0

    elif args.learn_action == "report":
        if args.format == "json":
            scores = compute_effectiveness(target)
            cands = cluster_unmatched_errors(target) + generate_from_resolved_cases(target)
            gaps = analyze_gaps(target)
            print(json.dumps({
                "effectiveness": [dc_asdict(s) for s in scores],
                "candidates": [dc_asdict(c) for c in cands],
                "gaps": gaps,
            }, ensure_ascii=False, indent=2))
        else:
            print(render_report(target))
        return 0

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="皮皮虾医生（OpenClaw Doctor）v5.1 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check", help="运行只读健康检查")
    p.add_argument("--target", default=".")
    p.add_argument("--baseline-file", help="可选的基线 JSON 文件")
    p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p.set_defaults(func=command_check)

    p = sub.add_parser("match", help="匹配错误文本到药方")
    p.add_argument("--text", default="")
    p.add_argument("--file")
    p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p.set_defaults(func=command_match)

    p = sub.add_parser("plan", help="生成确认前修复计划")
    p.add_argument("--text", default="")
    p.add_argument("--rx-id", default="")
    p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p.set_defaults(func=command_plan)

    p = sub.add_parser("record", help="写入脱敏病历")
    p.add_argument("--case-dir", default=".doctor/cases")
    p.add_argument("--title", required=True)
    p.add_argument("--status", choices=["fixed", "partial", "blocked"], required=True)
    p.add_argument("--summary", required=True)
    p.set_defaults(func=command_record)

    p = sub.add_parser("search", help="搜索病历")
    p.add_argument("--case-dir", default=".doctor/cases")
    p.add_argument("--query", default="")
    p.set_defaults(func=command_search)

    p = sub.add_parser("route", help="路由飞书消息文本")
    p.add_argument("--text", required=True)
    p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p.set_defaults(func=command_route)

    p = sub.add_parser("validate", help="验证皮皮虾医生包结构")
    p.add_argument("--target", default=str(ROOT))
    p.set_defaults(func=command_validate)

    p = sub.add_parser("test", help="运行集成测试")
    p.add_argument("--target", default=str(ROOT))
    p.set_defaults(func=command_test)

    # --- v5.1: snapshot (数字遗产+复活) ---
    p = sub.add_parser("snapshot", help="Agent 快照与恢复 (数字遗产+复活)")
    p.add_argument("--target", default=".")
    p.add_argument("--snapshot-action", choices=["save", "list", "diff", "restore", "verify"], default="save", help="快照操作")
    p.add_argument("--snapshot-id", default="", help="快照 ID")
    p.add_argument("--other-snapshot-id", default="", help="对比用的第二个快照 ID")
    p.add_argument("--description", default="", help="快照描述")
    p.add_argument("--dry-run", action="store_true", help="预演模式（不实际恢复）")
    p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p.set_defaults(func=command_snapshot)

    # --- v5.1: learn (药方自学习) ---
    p = sub.add_parser("learn", help="药方自学习引擎")
    p.add_argument("--target", default=".")
    p.add_argument("--learn-action", choices=["feedback", "effectiveness", "candidates", "gaps", "report"], default="report", help="学习操作")
    p.add_argument("--rx-id", default="", help="药方 ID")
    p.add_argument("--query", default="", help="原始查询文本")
    p.add_argument("--score", type=int, default=0, help="匹配分")
    p.add_argument("--outcome", choices=["hit", "miss", "effective", "ineffective", "skipped"], default="miss")
    p.add_argument("--resolved", action="store_true", help="问题是否已解决")
    p.add_argument("--resolution", default="", help="解决方案描述")
    p.add_argument("--case-id", default="", help="关联病历 ID")
    p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p.set_defaults(func=command_learn)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
