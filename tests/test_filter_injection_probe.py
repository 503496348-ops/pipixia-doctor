import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from filter_injection_probe import validate_filters


def test_validate_filters_rejects_unknown_and_unsafe_values():
    errors = validate_filters({"user_id": "u", "hack": "$where", "session_id": ""})
    assert "unsupported filter key: hack" in errors
    assert "unsafe filter value: hack" in errors
    assert "empty filter value: session_id" in errors
