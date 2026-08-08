"""Map DOM form fields to truthful answers from canonical profile."""

import re
from dataclasses import dataclass, field
from typing import Any

from job_os.browser.field_catalog import FIELD_RULES
from job_os.services.application_data import lookup_application_answer


@dataclass
class FormField:
    tag: str
    field_type: str
    name: str
    field_id: str
    label: str
    required: bool = False


@dataclass
class FieldAnswer:
    selector_hint: str
    value: str
    field_type: str = "text"
    action: str = "fill"  # fill | select | upload | check


@dataclass
class FormPlan:
    fields: list[FieldAnswer] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class FormReasoner:
    """Heuristic field matcher — no site-specific selectors."""

    def plan(
        self,
        *,
        dom_fields: list[dict],
        profile: dict[str, Any],
        cover_letter: str | None = None,
        resume_path: str | None = None,
    ) -> FormPlan:
        plan = FormPlan()
        name_parts = (profile.get("full_name") or "").split()
        first = name_parts[0] if name_parts else ""
        last = name_parts[-1] if len(name_parts) > 1 else ""

        screening = profile.get("screening_answers", {})
        auth = profile.get("work_authorization", {})
        app_flat = profile.get("_application_flat") or {}

        for raw in dom_fields:
            field = FormField(
                tag=raw.get("tag", ""),
                field_type=(raw.get("type") or "").lower(),
                name=(raw.get("name") or "").lower(),
                field_id=(raw.get("id") or "").lower(),
                label=(raw.get("label") or "").lower(),
                required=bool(raw.get("required")),
            )
            key = f"{field.name} {field.field_id} {field.label}".strip()
            hint = field.field_id or field.name or field.label

            if field.field_type == "file":
                if resume_path and any(k in key for k in ("resume", "cv", "curriculum")):
                    plan.fields.append(
                        FieldAnswer(selector_hint=hint, value=resume_path, field_type="file", action="upload")
                    )
                continue

            if field.field_type in ("checkbox", "radio"):
                answer = self._checkbox_answer(key, profile, auth, screening, app_flat)
                if answer is not None:
                    plan.fields.append(
                        FieldAnswer(selector_hint=hint, value=answer, field_type=field.field_type, action="check")
                    )
                continue

            if field.field_type == "select-one" or field.tag == "SELECT":
                answer = self._select_answer(key, profile, auth, screening, app_flat)
                if answer:
                    plan.fields.append(
                        FieldAnswer(selector_hint=hint, value=answer, field_type="select", action="select")
                    )
                continue

            text_value = self._text_answer(key, profile, first, last, cover_letter, screening, app_flat)
            if text_value is not None:
                plan.fields.append(
                    FieldAnswer(selector_hint=hint, value=text_value, field_type="text", action="fill")
                )

        if not plan.fields:
            plan.notes.append("no_fields_matched")
        return plan

    def _text_answer(
        self,
        key: str,
        profile: dict,
        first: str,
        last: str,
        cover_letter: str | None,
        screening: dict,
        app_flat: dict,
    ) -> str | None:
        catalog_ans = self._catalog_answer(key, app_flat)
        if catalog_ans is not None:
            return catalog_ans
        if any(k in key for k in ("notice period", "how soon", "days until", "join in")):
            days = app_flat.get("availability.notice_period_days", "0")
            if days == "0" or str(days).strip() in ("0", "immediate"):
                return app_flat.get("availability.start_date", "Immediate")
            return str(days)
        if any(k in key for k in ("salary", "compensation", "ctc", "pay")):
            return screening.get("desired_salary") or app_flat.get("compensation.desired_salary_usd_annual")
        if any(k in key for k in ("password", "passwd")):
            pwd = profile.get("account_password") or screening.get("password")
            return pwd
        if any(k in key for k in ("confirm password", "password confirmation", "retype password")):
            return profile.get("account_password") or screening.get("password")
        if any(k in key for k in ("username", "user name")) and "email" not in key:
            return profile.get("email")
        if any(k in key for k in ("sign up", "register", "create account")):
            return profile.get("email")
        if any(k in key for k in ("email", "e-mail")):
            return profile.get("email")
        if any(k in key for k in ("phone", "mobile", "tel")):
            return profile.get("phone")
        if "first" in key and "name" in key:
            return first
        if "last" in key and "name" in key:
            return last
        if key.strip() in ("name", "full name", "your name") or (
            "name" in key and "company" not in key and "username" not in key
        ):
            return profile.get("full_name")
        if "linkedin" in key:
            return profile.get("linkedin")
        if "github" in key:
            return profile.get("github")
        if any(k in key for k in ("city", "location")) and "company" not in key:
            return profile.get("location")
        if any(k in key for k in ("cover", "letter", "motivation", "why")):
            return (cover_letter or "")[:4000] if cover_letter else None
        if "university" in key or "school" in key or "institution" in key:
            return profile.get("education", {}).get("institution")
        if "degree" in key or "major" in key:
            return profile.get("education", {}).get("degree")
        if "gpa" in key:
            return str(profile.get("education", {}).get("gpa", ""))
        if "graduation" in key or "year" in key:
            return str(profile.get("education", {}).get("graduation_year", ""))

        for sk, sv in screening.items():
            if sk.lower() in key:
                return str(sv)

        return None

    def _catalog_answer(self, key: str, app_flat: dict) -> str | None:
        for patterns, dotted in FIELD_RULES:
            if any(p in key for p in patterns):
                val = lookup_application_answer(app_flat, dotted)
                if val:
                    return val
        return None

    def _select_answer(self, key: str, profile: dict, auth: dict, screening: dict, app_flat: dict) -> str | None:
        catalog = self._catalog_answer(key, app_flat)
        if catalog:
            return catalog
        if any(k in key for k in ("gender",)):
            return app_flat.get("demographics.gender", "Male")
        if any(k in key for k in ("veteran",)):
            return app_flat.get("demographics.veteran_status")
        if any(k in key for k in ("disability",)):
            return app_flat.get("demographics.disability_status")
        if any(k in key for k in ("previously employed", "former employee", "worked at")):
            return app_flat.get("company_screening.previously_employed_at_company", "No")
        if any(k in key for k in ("relative", "affiliated", "family")):
            return app_flat.get("company_screening.relative_employed_at_company", "No")
        if any(k in key for k in ("sponsor", "visa", "authorization", "work auth")):
            if auth.get("requires_sponsorship"):
                return "Yes"
            return "No"
        if "country" in key:
            return profile.get("location", "India").split(",")[-1].strip()
        for sk, sv in screening.items():
            if sk.lower() in key:
                return str(sv)
        return None

    def _checkbox_answer(self, key: str, profile: dict, auth: dict, screening: dict, app_flat: dict) -> str | None:
        if any(k in key for k in ("previously employed", "former")):
            return "no"
        if any(k in key for k in ("relative", "affiliated")):
            return "no"
        if any(k in key for k in ("veteran",)):
            return "no"
        if any(k in key for k in ("disability",)):
            return "no"
        if any(k in key for k in ("sponsor", "visa", "require sponsorship")):
            return "yes" if auth.get("requires_sponsorship") else "no"
        if any(k in key for k in ("relocate", "willing to relocate")):
            return "yes" if auth.get("willing_to_relocate", True) else "no"
        if "authorized" in key and "work" in key:
            return "no" if auth.get("requires_sponsorship") else "yes"
        for sk, sv in screening.items():
            if sk.lower() in key:
                return str(sv).lower()
        return None

    def detect_ats(self, url: str) -> str:
        lower = url.lower()
        if "greenhouse.io" in lower or "boards.greenhouse" in lower:
            return "greenhouse"
        if "lever.co" in lower or "jobs.lever" in lower:
            return "lever"
        if "workday" in lower:
            return "workday"
        if "ashbyhq.com" in lower:
            return "ashby"
        return "generic"
