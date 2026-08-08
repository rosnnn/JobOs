"""Merge application questionnaire defaults into profile for form filling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from job_os.config import get_settings


def _deep_get(data: dict, dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def load_application_defaults() -> dict[str, Any]:
    path = get_settings().user_profile_path.parent / "application_defaults.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def merge_application_profile(base_profile: dict[str, Any]) -> dict[str, Any]:
    """Full profile dict used by browser apply (resume + screening + ATS answers)."""
    merged = dict(base_profile)
    defaults = load_application_defaults()
    app_answers = merged.get("application_answers") or defaults
    if defaults:
        app_answers = {**defaults, **(merged.get("application_answers") or {})}

    screening = dict(merged.get("screening_answers") or {})
    demographics = app_answers.get("demographics") or {}
    compensation = app_answers.get("compensation") or {}
    company = app_answers.get("company_screening") or {}
    auth_ans = app_answers.get("work_authorization_answers") or {}
    avail = app_answers.get("availability") or {}

    screening.update(
        {
            "gender": demographics.get("gender", "Male"),
            "veteran_status": demographics.get("veteran_status", "I am not a protected veteran"),
            "disability_status": demographics.get("disability_status", "No, I do not have a disability"),
            "desired_salary": compensation.get("desired_salary_usd_annual", "45000"),
            "salary_expectations": compensation.get("salary_notes", ""),
            "previously_employed": company.get("previously_employed_at_company", "No"),
            "relative_at_company": company.get("relative_employed_at_company", "No"),
            "how_did_you_hear": app_answers.get("how_did_you_hear", "Job board"),
            "start_date": avail.get("start_date", "Immediate"),
            "notice_period_days": avail.get("notice_period_days", "0"),
        }
    )

    merged["application_answers"] = app_answers
    merged["screening_answers"] = screening
    merged["_application_flat"] = _flatten_answers(app_answers)
    return merged


def _flatten_answers(app: dict[str, Any], prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in app.items():
        key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            out.update(_flatten_answers(v, key))
        elif v is not None:
            out[key] = str(v)
    return out


def save_application_answers(updates: dict[str, Any]) -> dict[str, Any]:
    path = get_settings().user_profile_path
    profile = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    current = profile.get("application_answers") or load_application_defaults()
    profile["application_answers"] = _deep_merge(current, updates)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    # Also persist defaults file for reference
    defaults_path = path.parent / "application_defaults.json"
    defaults_path.write_text(json.dumps(profile["application_answers"], indent=2), encoding="utf-8")
    return profile["application_answers"]


def _deep_merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def lookup_application_answer(flat: dict[str, str], dotted_key: str) -> str | None:
    return flat.get(dotted_key)
