#!/usr/bin/env python3
"""皮皮虾医生（OpenClaw Doctor）v5.0 — 统一 CLI 入口"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def check(name: str, ok: bool, fix: str="") -> bool:
    mark = "OK" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {fix}" if (not ok and fix) else ""))
    return ok

def run_raven_bridge_check() -> bool:
    target = ROOT / 'scripts' / 'raven_bridge.py'
    if not target.exists():
        return check('raven_bridge.py exists', False, '新增 scripts/raven_bridge.py')
    try:
        subprocess.check_call([sys.executable, str(target), '--repo', str(ROOT), '--smoke'])
        return check('raven bridge smoke', True)
    except Exception as exc:
        return check('raven bridge smoke', False, f'run python scripts/raven_bridge.py --smoke: {exc}')


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--check', choices=['all','core','raven-bridge','raven'], default='all')
    args=parser.parse_args()

    print(f"== Doctor: {ROOT.name} ==")
    ok = True
    if args.check in ('all','core'):
        ok &= check('README.md exists', (ROOT/'README.md').exists(), '缺 README，用户无法按步骤安装')
        ok &= check('SKILL.md exists', (ROOT/'SKILL.md').exists(), '缺 SKILL.md，产品说明不完整')
        ok &= check('install.sh exists', (ROOT/'install.sh').exists(), '运行: bash install.sh')
        ok &= check('setup.py exists', (ROOT/'scripts/setup.py').exists(), '缺一键 setup 入口')
        ok &= check('smoke.py exists', (ROOT/'scripts/smoke.py').exists(), '缺核心 smoke 入口')
        ok &= check('python available', shutil.which('python3') is not None or shutil.which('python') is not None, '请安装 Python 3')
        pkg = ROOT / 'package.json'
        if pkg.exists():
            try:
                scripts = json.loads(pkg.read_text()).get('scripts', {})
            except Exception as exc:
                ok &= check('package.json parseable', False, f'JSON 解析失败: {exc}')
                scripts = {}
            for script in ['setup','doctor','smoke','test']:
                ok &= check(f'npm script {script}', script in scripts, f'在 package.json scripts 中补充 {script}')
        gate = ROOT / 'scripts/product_convergence_gate.py'
        if gate.exists():
            try:
                subprocess.check_call([sys.executable, str(gate), '--json'], cwd=ROOT, stdout=subprocess.DEVNULL)
                ok &= check('product convergence gate', True)
            except Exception:
                ok &= check('product convergence gate', False, '运行 python scripts/product_convergence_gate.py --json 查看详情')

    if args.check in ('all','raven','raven-bridge'):
        ok &= run_raven_bridge_check()

    print('doctor result:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1

if __name__ == '__main__':
    raise SystemExit(main())
