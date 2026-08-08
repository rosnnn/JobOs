"""Derive job-search preferences and discovery queries from parsed resume/profile."""

from __future__ import annotations

import re
from typing import Any

from job_os.services.profile_service import ProfileService

# Generic role hints — matched against parsed headline/employment, not hardcoded user roles
ROLE_HINTS = (
    "software engineer",
    "software developer",
    "developer",
    "engineer",
    "backend",
    "frontend",
    "full stack",
    "fullstack",
    "devops",
    "sre",
    "data engineer",
    "ml engineer",
    "machine learning",
    "intern",
    "graduate",
    "analyst",
    "consultant",
    "designer",
    "manager",
    "architect",
)


def _location_parts(profile: dict[str, Any]) -> tuple[str, str]:
    loc = str(profile.get("location") or "").strip()
    if not loc:
        auth = profile.get("work_authorization") or {}
        loc = str(auth.get("current") or "")
    parts = [p.strip() for p in loc.split(",") if p.strip()]
    city = parts[0] if parts else ""
    country = parts[-1] if len(parts) > 1 else (parts[0] if len(parts) == 1 else "")
    return city, country


def _parse_cities_from_profile(profile: dict[str, Any]) -> list[str]:
    city, country = _location_parts(profile)
    cities: list[str] = []
    for part in (city, country):
        if part and part.lower() not in cities:
            cities.append(part.lower())
    inst = (profile.get("education") or {}).get("institution") or ""
    if inst:
        for token in re.findall(r"[A-Za-z]{3,}", inst):
            if token.lower() not in cities and len(token) > 3:
                pass  # don't flood with institution words
    return cities


def _title_case_location(name: str) -> str:
    if not name:
        return name
    return " ".join(w.capitalize() if w.islower() or w.isupper() else w for w in name.split())


def _extract_target_roles(profile: dict[str, Any]) -> list[str]:
    roles: list[str] = []
    blob = " ".join(
        filter(
            None,
            [
                profile.get("headline"),
                profile.get("summary"),
                profile.get("experience_type"),
            ],
        )
    ).lower()
    for emp in profile.get("employment") or []:
        title = str(emp.get("title", "")).strip()
        if title and title.lower() not in roles:
            roles.append(title.lower())
        blob += " " + title.lower()

    for hint in ROLE_HINTS:
        if hint in blob and hint not in roles:
            roles.append(hint)

    if not roles:
        roles = ["developer"]
    return roles[:12]


def _keywords_from_profile(profile: dict[str, Any]) -> list[str]:
    keywords: list[str] = []
    for skill in profile.get("skills") or []:
        s = str(skill).strip()
        if len(s) >= 2 and not s.endswith(":"):
            keywords.append(s.lower())
    for role in _extract_target_roles(profile):
        keywords.append(role)
    for proj in profile.get("projects") or []:
        for tech in proj.get("technologies") or []:
            keywords.append(str(tech).lower())
    seen: set[str] = set()
    out: list[str] = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _adzuna_country_code(home_country: str) -> str:
    h = home_country.lower().strip()
    if not h:
        return "us"
    if "india" in h or h == "in":
        return "in"
    if any(x in h for x in ("united states", "usa", "u.s.", "america")) or h == "us":
        return "us"
    if any(x in h for x in ("united kingdom", "england", "scotland", "wales")) or h in ("uk", "gb"):
        return "gb"
    if "canada" in h or h == "ca":
        return "ca"
    if "australia" in h or h == "au":
        return "au"
    return "us"


def build_job_search_block(profile: dict[str, Any]) -> dict[str, Any]:
    auth = profile.get("work_authorization") or {}
    exp_years = float(profile.get("experience_years") or 0)
    city, country = _location_parts(profile)
    primary_city = _title_case_location(city) if city else _title_case_location(country)
    home = str(auth.get("current") or country or city or "").strip()
    if not home and profile.get("location"):
        home = str(profile.get("location")).split(",")[-1].strip()

    cities = _parse_cities_from_profile(profile)
    roles = _extract_target_roles(profile)
    requires_sponsor = bool(auth.get("requires_sponsorship", True))
    fresher = (
        exp_years <= 2
        or "intern" in str(profile.get("experience_type", "")).lower()
        or "graduate" in str(profile.get("experience_type", "")).lower()
    )

    location_label = primary_city or home or "remote"
    primary_role = roles[0] if roles else "developer"
    city_label = _title_case_location(city) if city else ""
    country_label = _title_case_location(country) if country else ""

    # Tier 1: city → Tier 2: country → Tier 3: global remote
    city_queries: list[str] = []
    country_queries: list[str] = []
    global_queries: list[str] = []

    for role in roles[:6]:
        if city_label:
            city_queries.append(f"{role} {city_label}")
            if fresher and "intern" not in role.lower() and "apprentice" not in role.lower():
                city_queries.append(f"{role} intern {city_label}")
        if country_label and country_label.lower() != (city_label or "").lower():
            country_queries.append(f"{role} {country_label}")
            if fresher and "intern" not in role.lower() and "apprentice" not in role.lower():
                country_queries.append(f"{role} intern {country_label}")
        global_queries.append(f"{role} remote")
        if fresher:
            global_queries.append(f"{role} intern remote")

    if requires_sponsor:
        global_queries.append(f"{primary_role} visa sponsorship remote")
        if country_label:
            country_queries.append(f"{primary_role} visa sponsorship {country_label}")

    discovery_himalayas = list(
        dict.fromkeys(city_queries[:3] + country_queries[:3] + global_queries[:4])
    )

    adzuna_country = _adzuna_country_code(home)
    discovery_adzuna = list(
        dict.fromkeys(
            city_queries[:6]
            + country_queries[:6]
            + [
                f"{primary_role} {location_label}",
                f"{primary_role} {'intern' if fresher else ''} {location_label}".strip(),
            ]
        )
    )
    for skill in (profile.get("skills") or [])[:8]:
        s = str(skill).strip()
        if len(s) >= 2 and not s.endswith(":"):
            if city_label:
                discovery_adzuna.append(f"{s} {primary_role} {city_label}")
            discovery_adzuna.append(f"{s} {primary_role} remote")

    # JSearch / Google for Jobs — LinkedIn, Indeed, Glassdoor, Naukri, ZipRecruiter, …
    discovery_jsearch: list[str] = []
    for role in roles[:6]:
        if city_label and country_label:
            discovery_jsearch.append(f"{role} in {city_label} {country_label}")
            if fresher:
                discovery_jsearch.append(f"{role} intern in {city_label} {country_label}")
        elif country_label:
            discovery_jsearch.append(f"{role} in {country_label}")
        discovery_jsearch.append(f"{role} remote")
    if requires_sponsor:
        discovery_jsearch.append(f"{primary_role} visa sponsorship remote")

    discovery_findwork = [f"{r} remote" for r in roles[:5]]

    discovery_queries: dict[str, list[str]] = {
        "jsearch": list(dict.fromkeys(discovery_jsearch)),
        "himalayas": discovery_himalayas,
        "findwork": list(dict.fromkeys(discovery_findwork)),
        "linkedin": list(dict.fromkeys(discovery_jsearch[:18])),
        "wellfound": list(dict.fromkeys(global_queries[:12] + country_queries[:8])),
        f"adzuna_{adzuna_country}": list(dict.fromkeys(discovery_adzuna)),
    }
    for cc in ("in", "us", "gb", "au", "ca", "de", "sg"):
        key = f"adzuna_{cc}"
        if key not in discovery_queries:
            discovery_queries[key] = list(dict.fromkeys(discovery_adzuna[:8]))
    if requires_sponsor:
        discovery_queries["adzuna_us"] = list(
            dict.fromkeys(discovery_queries.get("adzuna_us", []) + [f"{r} remote visa sponsorship" for r in roles[:5]])
        )

    return {
        "home_country": home,
        "adzuna_home": adzuna_country,
        "preferred_cities": cities,
        "primary_city": primary_city,
        "city": city_label,
        "country": country_label,
        "requires_sponsorship": requires_sponsor,
        "willing_to_relocate": bool(auth.get("willing_to_relocate", True)),
        "target_roles": roles,
        "keywords": _keywords_from_profile(profile),
        "experience_years": exp_years,
        "fresher_mode": fresher,
        "discovery_queries": discovery_queries,
        "location_tiers": {
            "city": city_label,
            "country": country_label,
        },
    }


def merge_prefs_with_profile(file_prefs: dict[str, Any], profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or ProfileService().load()
    js = profile.get("job_search") or build_job_search_block(profile)

    merged = dict(file_prefs)
    merged["keywords"] = list(dict.fromkeys((js.get("keywords") or []) + file_prefs.get("keywords", [])))
    merged["locations"] = js.get("preferred_cities") or file_prefs.get("locations", [])
    merged["requires_sponsorship_profile"] = js.get("requires_sponsorship")
    merged["fresher_mode"] = js.get("fresher_mode", True)
    merged["experience_years"] = js.get("experience_years", 0)
    merged["primary_city"] = js.get("primary_city")
    merged["home_country"] = js.get("home_country")
    merged["target_roles"] = js.get("target_roles", [])
    merged["discovery_queries"] = js.get("discovery_queries", {})
    merged["profile_derived"] = True
    return merged


def sync_profile_to_preferences(profile: dict[str, Any] | None = None) -> dict[str, Any]:
    from job_os.config import get_settings

    profile = profile or ProfileService().load()
    profile["job_search"] = build_job_search_block(profile)
    ProfileService().save(profile)

    prefs_path = get_settings().job_preferences_path
    file_prefs: dict[str, Any] = {}
    if prefs_path.exists():
        import json

        file_prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
    merged = merge_prefs_with_profile(file_prefs, profile)
    prefs_path.parent.mkdir(parents=True, exist_ok=True)
    prefs_path.write_text(
        __import__("json").dumps(merged, indent=2),
        encoding="utf-8",
    )
    return merged
