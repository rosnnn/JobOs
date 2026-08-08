"""Cross-source job deduplication by company + title fingerprint."""

from __future__ import annotations

import hashlib
import re


def normalize_company(name: str | None) -> str:
    if not name:
        return ""
    s = name.lower().strip()
    s = re.sub(r"\b(inc|llc|ltd|pvt|private|limited|corp|co)\b\.?", "", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_title(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def job_fingerprint(company_name: str | None, title: str) -> str:
    base = f"{normalize_company(company_name)}|{normalize_title(title)}"
    return hashlib.sha256(base.encode()).hexdigest()[:24]
