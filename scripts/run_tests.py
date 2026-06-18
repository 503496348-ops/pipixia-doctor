#!/usr/bin/env python3
"""Run the OpenClaw Doctor package smoke tests.

v4.1: added negative cases (regression / input validation) and
use TemporaryDirectory to avoid leaking test artifacts.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestCase:
    name: str
    command: list[str]
    expect: str
    cwd: Path
    exit_codes: tuple[int, ...] = (0,)


def run_case(case: TestCase) -> tuple[bool, str]:
    proc = subprocess.run(case.command, cwd=str(case.cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
    output = proc.stdout.strip()
    ok = proc.returncode in case.exit_codes and case.expect in output
    return ok, output


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OpenClaw Doctor smoke tests")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    workspace = root.parent
    py = sys.executable

    # Use TemporaryDirectory so the case dir is auto-cleaned on exit,
    # even when a test crashes or the process is killed.
    case_dir_cm = tempfile.TemporaryDirectory(prefix="doctor-tests-")
    case_dir = Path(case_dir_cm.name)

    try:
        tests = [
            # ----- happy path / smoke -----
            TestCase("validate", [py, str(root / "scripts" / "validate_skill.py"), str(root)], "OK", workspace),
            TestCase("health", [py, str(root / "scripts" / "doctor_check.py"), "--target", str(root), "--format", "markdown"], "已通过检查", workspace),
            TestCase("health-json", [py, str(root / "scripts" / "doctor_check.py"), "--target", str(root), "--format", "json"], '"passed_checks"', workspace),
            TestCase("auth-rx", [py, str(root / "scripts" / "prescription_match.py"), "--text", "missing_scope docx:document:readonly"], "RX-AUTH-001", workspace),
            TestCase("dep-rx", [py, str(root / "scripts" / "prescription_match.py"), "--text", "ModuleNotFoundError: No module named requests"], "RX-DEP-001", workspace),
            TestCase("repair-plan", [py, str(root / "scripts" / "repair_plan.py"), "--text", "rm -rf /"], "RX-REPAIR-002", workspace),
            TestCase("record", [py, str(root / "scripts" / "doctor_record.py"), "--case-dir", str(case_dir), "--title", "missing_scope", "--status", "fixed", "--summary", "ok"], str(case_dir), workspace),
            TestCase("case-search", [py, str(root / "scripts" / "case_search.py"), "--case-dir", str(case_dir), "--query", "missing_scope"], "missing_scope", workspace),
            TestCase("feishu-route", [py, str(root / "scripts" / "feishu_route.py"), "--text", "皮皮虾医生 帮我修一下：missing_scope docx:document:readonly", "--format", "json"], '"confirmation_required": true', workspace),
            # ----- negative / regression cases -----
            # doctor_check on a non-existent path should report RX-FILE-001 and exit non-zero.
            TestCase("missing-path", [py, str(root / "scripts" / "doctor_check.py"), "--target", "/no/such/path"], "RX-FILE-001", workspace, (2,)),
            # doctor_record with secret payload should be redacted before persisting.
            TestCase("redact-secret", [py, str(root / "scripts" / "doctor_record.py"), "--case-dir", str(case_dir), "--title", "leak-test", "--status", "blocked", "--summary", "token=ghp_abcdefghijklmnopqrstuvwxyz0123456789ABCD"], str(case_dir), workspace),
            # feishu_route with unknown intent should fall back to a health check.
            TestCase("route-fallback", [py, str(root / "scripts" / "feishu_route.py"), "--text", "随便说点什么没有触发词", "--format", "json"], '"fallback_report"', workspace),
            # ----- v5.0 new modules (HEARTBEAT + PCEC) -----
            TestCase("heartbeat", [py, str(root / "scripts" / "heartbeat.py"), "--target", str(root), "--rounds", "1"], "🦐 皮皮虾医生 HEARTBEAT", workspace),
            TestCase("heartbeat-json", [py, str(root / "scripts" / "heartbeat.py"), "--target", str(root), "--rounds", "1", "--format", "json"], '"findings"', workspace),
            TestCase("pcec", [py, str(root / "scripts" / "pcec_engine.py"), "--target", str(root), "--rounds", "1"], "🦐 皮皮虾医生 PCEC", workspace),
            TestCase("pcec-json", [py, str(root / "scripts" / "pcec_engine.py"), "--target", str(root), "--rounds", "1", "--format", "json"], '"outcomes"', workspace),
            # ----- v5.0 Week 2: 病历 MD5 + 三重备份 -----
            TestCase("case-verify-build", [py, str(root / "scripts" / "case_verify.py"), "--case-dir", str(case_dir), "--index", str(case_dir.parent / "index.json"), "--mode", "build"], "✅ 索引已构建", workspace),
            TestCase("case-verify-mode", [py, str(root / "scripts" / "case_verify.py"), "--case-dir", str(case_dir), "--index", str(case_dir.parent / "index.json"), "--mode", "verify"], "病历完整性校验", workspace),
            # ----- v5.0 Week 3: P1 增强 (十步法+日常保健+专科门诊) -----
            TestCase("ten-step-wizard", [py, str(root / "scripts" / "ten_step_method.py"), "--mode", "wizard", "--step", "1"], "🦐 皮皮虾医生 锋式十步法", workspace),
            TestCase("ten-step-demo", [py, str(root / "scripts" / "ten_step_method.py"), "--mode", "demo"], "锋式十步法 · 完整诊断", workspace),
            TestCase("health-maint", [py, str(root / "scripts" / "health_maintenance.py"), "--act", "daily", "--target", str(root)], "🦐 皮皮虾医生 日常保健三部曲", workspace),
            # ----- v5.0.2: Health Score 基线 -----
            TestCase("health-score", [py, str(root / "scripts" / "health_score.py"), "--score", "75", "--status", "ok"], "🦐 皮皮虾医生 Health Score", workspace),
        ]

        failures = 0
        for case in tests:
            ok, output = run_case(case)
            print(f"{'OK' if ok else 'FAIL'} {case.name}")
            if not ok:
                failures += 1
                print(output[:1200])

        # Extra assertion for redact-secret: check files in case_dir
        # Note: doctor_record.py generates {timestamp}-{slug}.md filenames
        if "redact-secret" in [c.name for c in tests]:
            try:
                case_files = list(sorted(case_dir.glob("*.md"), reverse=True))
                if case_files:
                    written = case_files[0].read_text(encoding="utf-8", errors="replace")
                    if "ghp_abcdefghijklmnopqrstuvwxyz0123456789ABCD" in written:
                        print(f"FAIL redact-secret persisted: ghp_ token leaked to {case_files[0]}")
                        failures += 1
                    elif "[REDACTED]" not in written and "redacted" not in written.lower():
                        print(f"FAIL redact-secret missing REDACTED marker in {case_files[0]}")
                        failures += 1
            except OSError as exc:
                print(f"FAIL redact-secret: check failed - {exc}")
                failures += 1

        print(f"summary: {len(tests) - failures}/{len(tests)} passed")
        return 1 if failures else 0
    finally:
        # Explicit cleanup; TemporaryDirectory.__exit__ would also work via context manager,
        # but using it explicitly keeps the suite readable.
        try:
            shutil.rmtree(case_dir, ignore_errors=True)
        finally:
            case_dir_cm.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
