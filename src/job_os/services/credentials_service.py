"""Local credential storage for runtime connectors (Gmail, boards, LLM keys)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from job_os.config import get_settings


class CredentialsService:
    def __init__(self, path: Path | None = None):
        settings = get_settings()
        self._path = path or (settings.user_profile_path.parent / "credentials.json")

    def load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save(self, data: dict[str, Any]) -> dict[str, Any]:
        existing = self.load()
        merged = {**existing, **data}
        # Normalize blank strings to null for consistent behavior.
        cleaned = {
            k: (v.strip() if isinstance(v, str) else v)
            for k, v in merged.items()
        }
        cleaned = {k: (None if v == "" else v) for k, v in cleaned.items()}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(cleaned, indent=2), encoding="utf-8")
        return cleaned

    @staticmethod
    def mask(value: str | None) -> str | None:
        if not value:
            return None
        if len(value) <= 6:
            return "*" * len(value)
        return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"
