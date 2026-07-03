"""Validate retrieval filters before they reach memory or vector stores."""
from __future__ import annotations

from typing import Mapping

ALLOWED_FILTER_KEYS = {"user_id", "session_id", "namespace", "created_after", "created_before"}
DENIED_VALUE_FRAGMENTS = ("$where", "javascript:", "__proto__", "../", "..\\")


def validate_filters(filters: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    for key, value in filters.items():
        if key not in ALLOWED_FILTER_KEYS:
            errors.append(f"unsupported filter key: {key}")
        if value in (None, ""):
            errors.append(f"empty filter value: {key}")
        text = str(value).lower()
        if any(fragment in text for fragment in DENIED_VALUE_FRAGMENTS):
            errors.append(f"unsafe filter value: {key}")
    return errors
