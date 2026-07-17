#!/usr/bin/env python3
"""Pipixia Raven-like memory bridge PoC."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import uuid
from datetime import datetime, timezone


@dataclass(frozen=True)
class Memory:
    text: str
    score: float = 0.0
    metadata: dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            object.__setattr__(self, 'metadata', {})


def _normalize_text(value: str) -> str:
    return (value or '').strip().lower()


def _from_dict(raw: dict[str, Any]) -> Memory:
    return Memory(
        text=str(raw.get('text', '')),
        score=float(raw.get('score', 0.0) or 0.0),
        metadata=dict(raw.get('metadata', {})),
    )


class FileMemoryBackend:
    def __init__(self, store_path: Path) -> None:
        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def _read_lines(self):
        if not self.store_path.exists():
            return []
        rows = []
        for line in self.store_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                rows.append({'text': 'invalid json line', 'score': 0.0, 'metadata': {}})
        return rows

    def _append(self, rec: dict[str, Any]) -> None:
        with self.store_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    async def recall(self, query: str, *, user_id: str | None = None, agent_id: str | None = None, top_k: int = 5):
        q = _normalize_text(query)
        out = []
        for row in self._read_lines():
            hit = _from_dict(row)
            meta = row.get('metadata', {})
            if user_id and meta.get('user_id') and meta.get('user_id') != user_id:
                continue
            if agent_id and meta.get('agent_id') and meta.get('agent_id') != agent_id:
                continue
            score = hit.score + (1.0 if q and q in _normalize_text(hit.text) else 0.0)
            out.append((score, hit))
        out.sort(key=lambda t: t[0], reverse=True)
        return [h for _s, h in out[:top_k]]

    async def store(self, session_id: str, messages: list[dict[str, Any]], *, user_id: str | None = None, agent_id: str | None = None, top_k: int | None = None) -> None:
        del top_k
        self._append({
            'id': str(uuid.uuid4()),
            'ts': datetime.now(timezone.utc).isoformat(),
            'session_id': session_id,
            'user_id': user_id,
            'agent_id': agent_id,
            'messages': messages,
            'type': 'store',
            'text': ' '.join(m.get('content', '') for m in messages if isinstance(m, dict) and m.get('content')),
        })

    async def feedback(self, payload: dict[str, Any]) -> None:
        self._append({
            'id': str(uuid.uuid4()),
            'ts': datetime.now(timezone.utc).isoformat(),
            'type': 'feedback',
            'payload': payload,
        })


def make_backend(repo_root: Path) -> FileMemoryBackend:
    return FileMemoryBackend(repo_root / 'references' / 'wave7_raven_memory_store.jsonl')
