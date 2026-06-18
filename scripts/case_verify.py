#!/usr/bin/env python3
"""OpenClaw Doctor v5.0 — 病历完整性校验

Implements PRD 4.1.5 「病历管理」中的:
- MD5 校验
- 三重备份

每个病历文件写入时计算 MD5，存到 .doctor/index.json。
三重备份: 原始位置 + .doctor/cases/ + .doctor/cases/.bak/
启动时验证所有病历的 MD5 一致性，发现篡改立即告警。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class CaseRecord:
    """病历文件记录。"""

    path: str
    md5: str
    size: int
    mtime: str
    backup_paths: list[str]


def compute_md5(path: Path) -> str:
    """Compute MD5 hash of a file."""
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def backup_to_three(case_dir: Path, source: Path) -> list[str]:
    """实现三重备份：原始 + .bak1/ + .bak2/."""
    backups: list[str] = []
    bak1 = case_dir / ".bak1" / source.name
    bak2 = case_dir / ".bak2" / source.name
    for target in [bak1, bak2]:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        backups.append(str(target))
    return backups


def build_index(case_dir: Path) -> dict:
    """扫描病历目录，建立 MD5 索引。"""
    index: dict[str, dict] = {}
    if not case_dir.exists():
        return index
    for path in sorted(case_dir.glob("*.md")):
        if path.is_file():
            md5 = compute_md5(path)
            index[str(path)] = {
                "path": str(path),
                "md5": md5,
                "size": path.stat().st_size,
                "mtime": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
            }
    return index


def verify_index(case_dir: Path, stored_index: dict) -> tuple[list[str], list[str]]:
    """校验当前文件 vs 存储索引的 MD5。

    Returns (corrupted, missing) lists.
    """
    current = build_index(case_dir)
    corrupted: list[str] = []
    missing: list[str] = []

    # 检查已记录的文件是否被篡改
    for path, info in stored_index.items():
        if path not in current:
            missing.append(path)
        else:
            if current[path]["md5"] != info["md5"]:
                corrupted.append(path)
            else:
                # MD5 一致，但还需校验 size 一致
                if current[path]["size"] != info["size"]:
                    corrupted.append(f"{path} (size mismatch)")

    # 检查新文件（未在索引中）
    new_files = set(current.keys()) - set(stored_index.keys())
    return corrupted, missing, list(new_files)


def repair_corrupted(case_dir: Path, corrupted: list[str]) -> int:
    """从备份恢复被篡改的文件。"""
    repaired = 0
    bak1 = case_dir / ".bak1"
    for path_str in corrupted:
        path = Path(path_str)
        for backup_dir in [bak1, case_dir / ".bak2"]:
            candidate = backup_dir / path.name
            if candidate.exists() and compute_md5(candidate) == compute_md5(path):
                # 不修复 — 备份与当前一致 = 备份也坏了
                continue
        # 尝试用最新的备份恢复
        for backup_dir in [case_dir / ".bak1", case_dir / ".bak2"]:
            candidate = backup_dir / path.name
            if candidate.exists():
                shutil.copy2(candidate, path)
                repaired += 1
                break
    return repaired


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenClaw Doctor 病历完整性校验")
    parser.add_argument("--case-dir", default=".doctor/cases", help="病历目录")
    parser.add_argument("--index", default=".doctor/index.json", help="MD5 索引文件")
    parser.add_argument("--mode", choices=["build", "verify", "backup"], default="verify", help="操作模式")
    parser.add_argument("--auto-repair", action="store_true", help="自动从备份恢复")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    case_dir = Path(args.case_dir).resolve()
    index_path = case_dir.parent / Path(args.index).name if not Path(args.index).is_absolute() else Path(args.index)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    if args.mode == "build":
        # 构建/重建索引
        index = build_index(case_dir)
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.format == "json":
            print(json.dumps({"mode": "build", "case_dir": str(case_dir), "files": len(index)}, ensure_ascii=False, indent=2))
        else:
            print(f"✅ 索引已构建：{len(index)} 个病历 → {index_path}")
        return 0

    if args.mode == "backup":
        # 三重备份所有病历
        if not case_dir.exists():
            print(f"❌ 病历目录不存在：{case_dir}")
            return 1
        backed_up = 0
        for path in case_dir.glob("*.md"):
            if path.is_file():
                backup_to_three(case_dir, path)
                backed_up += 1
        if args.format == "json":
            print(json.dumps({"mode": "backup", "backed_up": backed_up}, ensure_ascii=False))
        else:
            print(f"✅ 三重备份完成：{backed_up} 个文件")
        return 0

    # mode == "verify"
    if not index_path.exists():
        if args.format == "json":
            print(json.dumps({"mode": "verify", "status": "no_index", "msg": "索引不存在，先 build"}, ensure_ascii=False))
        else:
            print("⚠️ 索引不存在，请先运行 --mode build")
        return 1

    stored = json.loads(index_path.read_text(encoding="utf-8"))
    corrupted, missing, new_files = verify_index(case_dir, stored)

    if args.format == "json":
        result = {
            "mode": "verify",
            "case_dir": str(case_dir),
            "total_files": len(stored),
            "corrupted": corrupted,
            "missing": missing,
            "new_files": new_files,
            "status": "clean" if not corrupted and not missing else "tampered" if corrupted else "missing",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("🦐 皮皮虾医生 病历完整性校验报告")
        print()
        print(f"病历目录：{case_dir}")
        print(f"索引文件：{index_path}")
        print(f"已索引：{len(stored)} 个")
        print()
        if not corrupted and not missing:
            print("✅ 所有病历 MD5 一致，无篡改")
        else:
            if corrupted:
                print(f"🔴 发现篡改（{len(corrupted)} 个）：")
                for p in corrupted:
                    print(f"  - {p}")
            if missing:
                print(f"⚠️ 文件丢失（{len(missing)} 个）：")
                for p in missing:
                    print(f"  - {p}")
            if new_files:
                print(f"🆕 新增文件（{len(new_files)} 个）：")
                for p in new_files[:5]:
                    print(f"  - {p}")
                if len(new_files) > 5:
                    print(f"  ... 还有 {len(new_files) - 5} 个")

    if args.auto_repair and corrupted:
        repaired = repair_corrupted(case_dir, corrupted)
        print(f"\n🔧 自动修复：{repaired} 个文件已从备份恢复")

    return 0 if not corrupted else 2


if __name__ == "__main__":
    raise SystemExit(main())
