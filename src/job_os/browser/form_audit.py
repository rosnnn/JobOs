"""Record what each application form asked and what we filled."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FieldAuditEntry:
    page_index: int
    page_url: str
    label: str
    field_type: str
    required: bool
    status: str  # filled | skipped | captcha | readonly | upload
    value_filled: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page_index,
            "page_url": self.page_url,
            "question": self.label,
            "field_type": self.field_type,
            "required": self.required,
            "status": self.status,
            "filled": self.value_filled,
            "notes": self.notes,
        }


@dataclass
class FormAuditReport:
    ats: str = "generic"
    pages: list[FieldAuditEntry] = field(default_factory=list)
    captcha_detected: bool = False
    captcha_type: str | None = None
    account_signup_required: bool = False
    stopped_reason: str | None = None

    def add(
        self,
        *,
        page_index: int,
        page_url: str,
        label: str,
        field_type: str,
        required: bool,
        status: str,
        value: str | None = None,
        notes: str | None = None,
    ) -> None:
        display_val = value
        if value and len(value) > 120:
            display_val = value[:117] + "..."
        self.pages.append(
            FieldAuditEntry(
                page_index=page_index,
                page_url=page_url,
                label=label or "(unlabeled field)",
                field_type=field_type,
                required=required,
                status=status,
                value_filled=display_val,
                notes=notes,
            )
        )

    def summary(self) -> dict[str, Any]:
        filled = sum(1 for p in self.pages if p.status == "filled")
        skipped = sum(1 for p in self.pages if p.status == "skipped")
        by_page: dict[int, list[dict]] = {}
        for p in self.pages:
            by_page.setdefault(p.page_index, []).append(p.to_dict())
        return {
            "ats": self.ats,
            "total_fields_seen": len(self.pages),
            "filled": filled,
            "skipped": skipped,
            "captcha_detected": self.captcha_detected,
            "captcha_type": self.captcha_type,
            "account_signup_required": self.account_signup_required,
            "stopped_reason": self.stopped_reason,
            "by_page": by_page,
            "entries": [p.to_dict() for p in self.pages],
        }
