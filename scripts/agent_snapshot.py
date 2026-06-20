#!/usr/bin/env python3
"""OpenClaw Doctor v5.1 — Agent 快照与恢复引擎

Implements the core "数字遗产 + 复活" capability:
- Capture complete agent state as a versioned snapshot
- Diff between any two snapshots to see what changed
- Restore agent from a known-good snapshot
- List and manage snapshot history

Design:
- Snapshot = tar.gz of critical agent files + manifest.json with checksums
- Manifest includes: file hashes, sizes, timestamps, metadata
- Diff = compare two manifests + content-level diffs for changed files
- Restore = extract snapshot to target directory (with safety confirmations)

Brand: AtomCollide-智械工坊
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tarfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SNAPSHOT_DIR_NAME = ".doctor/snapshots"
MANIFEST_NAME = "manifest.json"

# Files/dirs that are part of an agent's "digital soul"
CRITICAL_FILES = [
    "SOUL.md",
    "AGENTS.md",
    "IDENTITY.md",
    "USER.md",
    "TOOLS.md",
    "MEMORY.md",
    "HEARTBEAT.md",
]

CRITICAL_DIRS = [
    "memory",
    "skills",
    "cron",
    "state",
    "evolution_gate",
    ".hermes-skill",
]

CRITICAL_PATTERNS = [
    "*.json",
    "*.yaml",
    "*.yml",
    "*.toml",
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FileEntry:
    """Metadata for a single file in a snapshot."""
    relative_path: str
    sha256: str
    size: int
    mtime: str


@dataclass
class SnapshotManifest:
    """Complete manifest of an agent snapshot."""
    snapshot_id: str
    created_at: str
    description: str
    agent_name: str
    total_files: int
    total_size: int
    files: list[FileEntry] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class DiffEntry:
    """A single difference between two snapshots."""
    change_type: str  # added | removed | modified | unchanged
    path: str
    old_sha256: str = ""
    new_sha256: str = ""
    old_size: int = 0
    new_size: int = 0


@dataclass
class SnapshotDiff:
    """Complete diff between two snapshots."""
    old_snapshot_id: str
    new_snapshot_id: str
    added: list[DiffEntry] = field(default_factory=list)
    removed: list[DiffEntry] = field(default_factory=list)
    modified: list[DiffEntry] = field(default_factory=list)
    unchanged_count: int = 0


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def compute_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_agent_files(target: Path) -> list[Path]:
    """Collect all critical agent files from a workspace."""
    collected: list[Path] = []
    ignored = {".git", "__pycache__", ".venv", "venv", "node_modules",
               ".doctor", ".pytest_cache", SNAPSHOT_DIR_NAME}

    # 1. Critical individual files
    for name in CRITICAL_FILES:
        path = target / name
        if path.exists() and path.is_file():
            collected.append(path)

    # 2. Critical directories (recursive scan)
    for dirname in CRITICAL_DIRS:
        dirpath = target / dirname
        if dirpath.exists() and dirpath.is_dir():
            for root, dirs, files in os.walk(dirpath):
                dirs[:] = [d for d in dirs if d not in ignored]
                for fname in files:
                    fpath = Path(root) / fname
                    if fpath.is_file():
                        collected.append(fpath)

    # 3. Root-level config files
    for pattern in CRITICAL_PATTERNS:
        for fpath in target.glob(pattern):
            if fpath.is_file() and fpath.parent == target:
                if fpath not in collected:
                    collected.append(fpath)

    # 4. SKILL.md in root
    skill_md = target / "SKILL.md"
    if skill_md.exists() and skill_md.is_file() and skill_md not in collected:
        collected.append(skill_md)

    return sorted(set(collected))


def generate_snapshot_id() -> str:
    """Generate a unique snapshot ID."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"snap-{ts}"


def create_manifest(target: Path, description: str = "") -> SnapshotManifest:
    """Create a manifest by scanning the agent workspace."""
    files = collect_agent_files(target)
    entries: list[FileEntry] = []
    total_size = 0

    for fpath in files:
        rel = str(fpath.relative_to(target))
        stat = fpath.stat()
        entry = FileEntry(
            relative_path=rel,
            sha256=compute_sha256(fpath),
            size=stat.st_size,
            mtime=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        )
        entries.append(entry)
        total_size += stat.st_size

    # Detect agent name from IDENTITY.md or directory name
    agent_name = target.name
    identity = target / "IDENTITY.md"
    if identity.exists():
        try:
            text = identity.read_text(encoding="utf-8", errors="replace")[:500]
            for line in text.splitlines():
                if line.startswith("# ") or line.startswith("name:"):
                    agent_name = line.lstrip("# ").split(":", 1)[-1].strip().strip('"')
                    break
        except Exception:
            pass

    return SnapshotManifest(
        snapshot_id=generate_snapshot_id(),
        created_at=datetime.now(timezone.utc).isoformat(),
        description=description,
        agent_name=agent_name,
        total_files=len(entries),
        total_size=total_size,
        files=entries,
    )


def save_snapshot(target: Path, description: str = "") -> Path:
    """Create and save a complete agent snapshot."""
    snapshot_dir = target / SNAPSHOT_DIR_NAME
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    manifest = create_manifest(target, description)

    # Create tar.gz archive
    archive_path = snapshot_dir / f"{manifest.snapshot_id}.tar.gz"
    with tarfile.open(str(archive_path), "w:gz") as tar:
        for entry in manifest.files:
            fpath = target / entry.relative_path
            if fpath.exists() and fpath.is_file():
                tar.add(str(fpath), arcname=entry.relative_path)

    # Save manifest alongside archive
    manifest_path = snapshot_dir / f"{manifest.snapshot_id}.json"
    manifest_path.write_text(
        json.dumps(asdict(manifest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return archive_path


def load_manifest(manifest_path: Path) -> SnapshotManifest:
    """Load a manifest from disk."""
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = [FileEntry(**f) for f in data.get("files", [])]
    data["files"] = files
    return SnapshotManifest(**data)


def list_snapshots(target: Path) -> list[dict]:
    """List all snapshots for a workspace."""
    snapshot_dir = target / SNAPSHOT_DIR_NAME
    if not snapshot_dir.exists():
        return []

    snapshots = []
    for manifest_path in sorted(snapshot_dir.glob("snap-*.json"), reverse=True):
        try:
            manifest = load_manifest(manifest_path)
            archive = snapshot_dir / f"{manifest.snapshot_id}.tar.gz"
            snapshots.append({
                "snapshot_id": manifest.snapshot_id,
                "created_at": manifest.created_at,
                "description": manifest.description,
                "agent_name": manifest.agent_name,
                "total_files": manifest.total_files,
                "total_size": manifest.total_size,
                "archive_exists": archive.exists(),
                "archive_size": archive.stat().st_size if archive.exists() else 0,
            })
        except Exception:
            continue

    return snapshots


def diff_snapshots(manifest_old: SnapshotManifest, manifest_new: SnapshotManifest) -> SnapshotDiff:
    """Compare two snapshots and return differences."""
    old_map = {f.relative_path: f for f in manifest_old.files}
    new_map = {f.relative_path: f for f in manifest_new.files}

    all_paths = sorted(set(old_map.keys()) | set(new_map.keys()))

    diff = SnapshotDiff(
        old_snapshot_id=manifest_old.snapshot_id,
        new_snapshot_id=manifest_new.snapshot_id,
    )

    for path in all_paths:
        old_entry = old_map.get(path)
        new_entry = new_map.get(path)

        if old_entry is not None and new_entry is None:
            diff.removed.append(DiffEntry(
                change_type="removed",
                path=path,
                old_sha256=old_entry.sha256,
                old_size=old_entry.size,
            ))
        elif new_entry is not None and old_entry is None:
            diff.added.append(DiffEntry(
                change_type="added",
                path=path,
                new_sha256=new_entry.sha256,
                new_size=new_entry.size,
            ))
        elif old_entry is not None and new_entry is not None and old_entry.sha256 != new_entry.sha256:
            diff.modified.append(DiffEntry(
                change_type="modified",
                path=path,
                old_sha256=old_entry.sha256,
                new_sha256=new_entry.sha256,
                old_size=old_entry.size,
                new_size=new_entry.size,
            ))
        else:
            diff.unchanged_count += 1

    return diff


def restore_snapshot(target: Path, snapshot_id: str, dry_run: bool = False) -> dict:
    """Restore an agent from a snapshot."""
    snapshot_dir = target / SNAPSHOT_DIR_NAME
    archive_path = snapshot_dir / f"{snapshot_id}.tar.gz"
    manifest_path = snapshot_dir / f"{snapshot_id}.json"

    if not archive_path.exists():
        return {"success": False, "error": f"Snapshot archive not found: {snapshot_id}"}

    if not manifest_path.exists():
        return {"success": False, "error": f"Snapshot manifest not found: {snapshot_id}"}

    manifest = load_manifest(manifest_path)

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "snapshot_id": snapshot_id,
            "would_restore": manifest.total_files,
            "files": [f.relative_path for f in manifest.files],
        }

    # Create backup of current state before restoring
    backup_id = generate_snapshot_id().replace("snap-", "pre-restore-")
    backup_archive = snapshot_dir / f"{backup_id}.tar.gz"
    try:
        save_snapshot(target, f"Auto-backup before restoring {snapshot_id}")
    except Exception:
        pass  # Non-fatal: we still try to restore

    # Extract snapshot
    restored = 0
    errors: list[str] = []
    with tarfile.open(str(archive_path), "r:gz") as tar:
        for member in tar.getmembers():
            try:
                # Security: prevent path traversal
                if member.name.startswith("/") or ".." in member.name:
                    errors.append(f"Skipped suspicious path: {member.name}")
                    continue
                tar.extract(member, path=str(target))
                restored += 1
            except Exception as e:
                errors.append(f"Failed to extract {member.name}: {e}")

    return {
        "success": len(errors) == 0,
        "snapshot_id": snapshot_id,
        "restored_files": restored,
        "errors": errors,
        "pre_restore_backup": str(backup_archive) if backup_archive.exists() else None,
    }


def verify_snapshot(target: Path, snapshot_id: str) -> dict:
    """Verify current state matches a snapshot's manifest."""
    snapshot_dir = target / SNAPSHOT_DIR_NAME
    manifest_path = snapshot_dir / f"{snapshot_id}.json"

    if not manifest_path.exists():
        return {"success": False, "error": f"Manifest not found: {snapshot_id}"}

    manifest = load_manifest(manifest_path)
    current_manifest = create_manifest(target)

    diff = diff_snapshots(manifest, current_manifest)

    return {
        "success": True,
        "snapshot_id": snapshot_id,
        "expected_files": manifest.total_files,
        "current_files": current_manifest.total_files,
        "added": len(diff.added),
        "removed": len(diff.removed),
        "modified": len(diff.modified),
        "unchanged": diff.unchanged_count,
        "matches": len(diff.added) == 0 and len(diff.removed) == 0 and len(diff.modified) == 0,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_manifest(manifest: SnapshotManifest) -> str:
    """Render a snapshot manifest as markdown."""
    lines = [
        "🦐 皮皮虾医生 Agent 快照",
        "",
        f"快照 ID：{manifest.snapshot_id}",
        f"创建时间：{manifest.created_at}",
        f"Agent 名称：{manifest.agent_name}",
        f"描述：{manifest.description or '(无)'}",
        f"文件总数：{manifest.total_files}",
        f"总大小：{manifest.total_size // 1024}KB",
        "",
        "## 文件清单",
    ]

    # Group by directory
    dirs: dict[str, list[FileEntry]] = {}
    for entry in manifest.files:
        d = str(Path(entry.relative_path).parent)
        dirs.setdefault(d, []).append(entry)

    for d in sorted(dirs.keys()):
        lines.append(f"\n### {d}/")
        for entry in dirs[d]:
            lines.append(f"  - {Path(entry.relative_path).name} ({entry.size}B, sha256:{entry.sha256[:12]}...)")

    return "\n".join(lines)


def render_diff(diff: SnapshotDiff) -> str:
    """Render a snapshot diff as markdown."""
    lines = [
        "🦐 皮皮虾医生 快照对比",
        "",
        f"旧快照：{diff.old_snapshot_id}",
        f"新快照：{diff.new_snapshot_id}",
        "",
        f"总计：+{len(diff.added)} 新增, ~{len(diff.modified)} 修改, -{len(diff.removed)} 删除, ={diff.unchanged_count} 未变",
    ]

    if diff.added:
        lines.extend(["", "## 新增文件"])
        for entry in diff.added:
            lines.append(f"  + {entry.path} ({entry.new_size}B)")

    if diff.removed:
        lines.extend(["", "## 删除文件"])
        for entry in diff.removed:
            lines.append(f"  - {entry.path} ({entry.old_size}B)")

    if diff.modified:
        lines.extend(["", "## 修改文件"])
        for entry in diff.modified:
            size_delta = entry.new_size - entry.old_size
            sign = "+" if size_delta >= 0 else ""
            lines.append(f"  ~ {entry.path} ({sign}{size_delta}B)")

    if not diff.added and not diff.removed and not diff.modified:
        lines.extend(["", "✅ 两个快照完全一致，无差异。"])

    return "\n".join(lines)


def render_list(snapshots: list[dict]) -> str:
    """Render snapshot list as markdown."""
    if not snapshots:
        return "🦐 皮皮虾医生 快照列表\n\n暂无快照。使用 `snapshot --mode save` 创建第一个快照。"

    lines = [
        "🦐 皮皮虾医生 快照列表",
        "",
        f"共 {len(snapshots)} 个快照：",
        "",
    ]

    for snap in snapshots:
        size_kb = snap["total_size"] // 1024
        archive_kb = snap.get("archive_size", 0) // 1024
        lines.extend([
            f"### {snap['snapshot_id']}",
            f"  时间：{snap['created_at']}",
            f"  Agent：{snap['agent_name']}",
            f"  描述：{snap['description'] or '(无)'}",
            f"  文件：{snap['total_files']} 个, {size_kb}KB",
            f"  归档：{archive_kb}KB {'✅' if snap['archive_exists'] else '❌ 缺失'}",
            "",
        ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="OpenClaw Doctor Agent 快照与恢复 (数字遗产+复活)"
    )
    parser.add_argument(
        "--target", default=".",
        help="Agent workspace directory",
    )
    parser.add_argument(
        "--mode",
        choices=["save", "list", "diff", "restore", "verify", "show"],
        default="save",
        help="Operation mode",
    )
    parser.add_argument("--snapshot-id", default="", help="Snapshot ID for diff/restore/verify/show")
    parser.add_argument("--other-snapshot-id", default="", help="Second snapshot ID for diff")
    parser.add_argument("--description", default="", help="Description for save")
    parser.add_argument("--dry-run", action="store_true", help="Dry run for restore")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    target = Path(args.target).resolve()

    if args.mode == "save":
        archive = save_snapshot(target, args.description)
        manifest_path = archive.parent / f"{archive.stem.replace('.tar', '')}.json"
        if args.format == "json":
            manifest = load_manifest(manifest_path)
            print(json.dumps(asdict(manifest), ensure_ascii=False, indent=2))
        else:
            manifest = load_manifest(manifest_path)
            lines = [
                "🦐 皮皮虾医生 Agent 快照已创建",
                "",
                f"快照 ID：{manifest.snapshot_id}",
                f"文件数：{manifest.total_files}",
                f"总大小：{manifest.total_size // 1024}KB",
                f"归档路径：{archive}",
                f"清单路径：{manifest_path}",
            ]
            print("\n".join(lines))
        return 0

    elif args.mode == "list":
        snapshots = list_snapshots(target)
        if args.format == "json":
            print(json.dumps(snapshots, ensure_ascii=False, indent=2))
        else:
            print(render_list(snapshots))
        return 0

    elif args.mode == "show":
        if not args.snapshot_id:
            print("ERROR: --snapshot-id is required for show mode")
            return 1
        manifest_path = target / SNAPSHOT_DIR_NAME / f"{args.snapshot_id}.json"
        if not manifest_path.exists():
            print(f"ERROR: Manifest not found: {args.snapshot_id}")
            return 1
        manifest = load_manifest(manifest_path)
        if args.format == "json":
            print(json.dumps(asdict(manifest), ensure_ascii=False, indent=2))
        else:
            print(render_manifest(manifest))
        return 0

    elif args.mode == "diff":
        if not args.snapshot_id or not args.other_snapshot_id:
            print("ERROR: --snapshot-id and --other-snapshot-id are both required for diff mode")
            return 1
        snap_dir = target / SNAPSHOT_DIR_NAME
        old_manifest_path = snap_dir / f"{args.snapshot_id}.json"
        new_manifest_path = snap_dir / f"{args.other_snapshot_id}.json"
        if not old_manifest_path.exists():
            print(f"ERROR: Old manifest not found: {args.snapshot_id}")
            return 1
        if not new_manifest_path.exists():
            print(f"ERROR: New manifest not found: {args.other_snapshot_id}")
            return 1
        old_manifest = load_manifest(old_manifest_path)
        new_manifest = load_manifest(new_manifest_path)
        diff = diff_snapshots(old_manifest, new_manifest)
        if args.format == "json":
            print(json.dumps(asdict(diff), ensure_ascii=False, indent=2))
        else:
            print(render_diff(diff))
        return 0

    elif args.mode == "restore":
        if not args.snapshot_id:
            print("ERROR: --snapshot-id is required for restore mode")
            return 1
        result = restore_snapshot(target, args.snapshot_id, dry_run=args.dry_run)
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if result.get("dry_run"):
                lines = [
                    "🦐 皮皮虾医生 快照恢复（预演模式）",
                    "",
                    f"快照 ID：{result['snapshot_id']}",
                    f"将恢复 {result['would_restore']} 个文件：",
                ]
                for f in result.get("files", []):
                    lines.append(f"  - {f}")
                lines.extend(["", "去除 --dry-run 以实际执行恢复。"])
            elif result["success"]:
                lines = [
                    "🦐 皮皮虾医生 快照恢复完成",
                    "",
                    f"快照 ID：{result['snapshot_id']}",
                    f"恢复文件：{result['restored_files']} 个",
                ]
                if result.get("pre_restore_backup"):
                    lines.append(f"自动备份：{result['pre_restore_backup']}")
            else:
                lines = [
                    "🦐 皮皮虾医生 快照恢复失败",
                    "",
                    f"快照 ID：{result['snapshot_id']}",
                    f"错误：{result.get('error', 'Unknown error')}",
                ]
                for err in result.get("errors", []):
                    lines.append(f"  - {err}")
            print("\n".join(lines))
        return 0 if result.get("success") or result.get("dry_run") else 1

    elif args.mode == "verify":
        if not args.snapshot_id:
            print("ERROR: --snapshot-id is required for verify mode")
            return 1
        result = verify_snapshot(target, args.snapshot_id)
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if result.get("matches"):
                lines = [
                    "🦐 皮皮虾医生 快照验证",
                    "",
                    f"快照 ID：{result['snapshot_id']}",
                    f"✅ 当前状态与快照完全一致（{result['expected_files']} 个文件）",
                ]
            else:
                lines = [
                    "🦐 皮皮虾医生 快照验证",
                    "",
                    f"快照 ID：{result['snapshot_id']}",
                    f"❌ 状态不一致：",
                    f"  预期文件：{result['expected_files']}",
                    f"  当前文件：{result['current_files']}",
                    f"  新增：{result['added']}",
                    f"  修改：{result['modified']}",
                    f"  删除：{result['removed']}",
                    f"  未变：{result['unchanged']}",
                ]
            print("\n".join(lines))
        return 0 if result.get("matches") else 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
