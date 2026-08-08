"""Location / visa eligibility from user profile — not hardcoded to one person."""

from __future__ import annotations

import re
from typing import Any

from job_os.services.profile_job_search import build_job_search_block

WORLDWIDE_MARKERS = (
    "worldwide",
    "world wide",
    "global",
    "anywhere",
    "any country",
    "anywhere in the world",
    "no location restriction",
    "no restrictions",
    "work from anywhere",
    "remote - global",
    "fully remote",
    "remote worldwide",
    "international candidates",
    "open to all countries",
)

# ISO-2 prefix glued to country on apply pages: deGermany, usUnited States, brBrazil
ISO_PREFIX_TO_COUNTRY: dict[str, str] = {
    "us": "united states",
    "uk": "united kingdom",
    "gb": "united kingdom",
    "de": "germany",
    "no": "norway",
    "se": "sweden",
    "dk": "denmark",
    "fi": "finland",
    "nl": "netherlands",
    "fr": "france",
    "es": "spain",
    "it": "italy",
    "at": "austria",
    "ch": "switzerland",
    "be": "belgium",
    "pl": "poland",
    "pt": "portugal",
    "cz": "czech republic",
    "ro": "romania",
    "hu": "hungary",
    "ie": "ireland",
    "ca": "canada",
    "au": "australia",
    "nz": "new zealand",
    "br": "brazil",
    "mx": "mexico",
    "ar": "argentina",
    "cl": "chile",
    "co": "colombia",
    "pe": "peru",
    "sg": "singapore",
    "jp": "japan",
    "kr": "south korea",
    "cn": "china",
    "tw": "taiwan",
    "hk": "hong kong",
    "in": "india",
    "ae": "united arab emirates",
    "sa": "saudi arabia",
    "il": "israel",
    "tr": "turkey",
    "za": "south africa",
    "ng": "nigeria",
    "eg": "egypt",
    "ph": "philippines",
    "id": "indonesia",
    "vn": "vietnam",
    "th": "thailand",
    "my": "malaysia",
    "ru": "russia",
    "ua": "ukraine",
}

# Any non-India country/region lock blocks India-based candidates without local auth
FOREIGN_LOCK_TERMS: frozenset[str] = frozenset(
    {
        *ISO_PREFIX_TO_COUNTRY.values(),
        "usa",
        "u.s.a",
        "u.s.",
        "u.k.",
        "eu",
        "european union",
        "europe",
        "emea",
        "latam",
        "apac",
        "mena",
        "north america",
        "south america",
        "scandinavia",
        "dach",
        "benelux",
        "ukraine",
        "russia",
        "china",
        "taiwan",
        "hong kong",
        "philippines",
        "indonesia",
        "vietnam",
        "thailand",
        "malaysia",
        "united arab emirates",
        "uae",
        "saudi arabia",
        "israel",
        "turkey",
        "south africa",
        "nigeria",
        "egypt",
        "mexico",
        "argentina",
        "chile",
        "colombia",
        "peru",
        "brazil",
        "poland",
        "portugal",
        "czech republic",
        "czechia",
        "romania",
        "hungary",
        "greece",
        "croatia",
        "serbia",
        "bulgaria",
        "slovakia",
        "slovenia",
        "estonia",
        "latvia",
        "lithuania",
        "luxembourg",
        "iceland",
        "qatar",
        "kuwait",
        "bahrain",
        "oman",
        "jordan",
        "lebanon",
        "pakistan",
        "bangladesh",
        "sri lanka",
        "nepal",
        "kenya",
        "ghana",
        "morocco",
        "tunisia",
        "algeria",
    }
)

# Sources that often omit country lock in API — apply-page enrichment used in discovery
GLOBAL_REMOTE_SOURCES = frozenset(
    {
        "remoteok",
        "remotive",
        "jobicy",
        "arbeitnow",
        "himalayas",
        "adzuna_us",
        "adzuna_gb",
        "greenhouse",
        "lever",
    }
)

ONLY_PHRASE_SKIP = frozenset(
    {
        "employee",
        "employees",
        "remote",
        "onsite",
        "on-site",
        "weekday",
        "weekdays",
        "business",
        "this",
        "that",
        "time",
        "citizen",
        "citizens",
        "us citizen",
        "uk citizen",
    }
)

COUNTRY_LOCK_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"\b[\w\s\-]{2,40}\s+only\b",
        r"\bonly\s+[\w\s\-]{2,40}\b",
        r"\bmust\s+be\s+(legally\s+)?(located|based|resident|living)\s+in\s+[\w\s\-]{2,40}",
        r"\beligible\s+to\s+work\s+in\s+(the\s+)?[\w\s\-]{2,40}",
        r"\blegally\s+authorized\s+to\s+work\s+in\s+(the\s+)?[\w\s\-]{2,40}",
        r"\bright\s+to\s+work\s+in\s+(the\s+)?[\w\s\-]{2,40}",
        r"\b(us|uk|eu)\s+citizen(s)?\s+(only|required)\b",
        r"\bcitizenship\s+required\b",
        r"\bwork\s+authorization\s+in\s+[\w\s\-]{2,40}\s+required\b",
    )
)

INDIA_ONSITE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"\bindia\b",
        r"\bbengaluru\b",
        r"\bbangalore\b",
        r"\bhyderabad\b",
        r"\bpune\b",
        r"\bchennai\b",
        r"\bmumbai\b",
        r"\bkarnataka\b",
        r"\bnoida\b",
        r"\bgurgaon\b",
        r"\bgurugram\b",
    )
)

POSITIVE_SPONSOR_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"visa\s+sponsorship\s+(available|provided|offered|yes|possible)",
        r"(will|can|do|we)\s+sponsor",
        r"sponsorship\s+(available|provided|offered|possible)",
        r"open\s+to\s+(visa\s+)?sponsor",
        r"h1b\s+sponsor",
        r"employment\s+visa\s+sponsor",
    )
)

NEGATIVE_SPONSOR_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"no\s+visa\s+sponsorship",
        r"no\s+sponsorship",
        r"unable\s+to\s+sponsor",
        r"cannot\s+sponsor",
        r"will\s+not\s+sponsor",
        r"without\s+sponsorship",
        r"not\s+(?:able|eligible)\s+to\s+sponsor",
        r"must\s+be\s+(legally\s+)?authorized\s+to\s+work",
        r"right\s+to\s+work\s+in",
    )
)

SENIOR_YOE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"\b[3-9]\+\s*years\b",
        r"\b10\+\s*years\b",
        r"\b5\+\s*years\b",
        r"\bminimum\s+[3-9]\s+years\b",
        r"\b(?:senior|staff|principal|lead)\s+(?:software|engineer|developer)\b",
    )
)


def _strip_iso_prefix(text: str) -> str:
    t = text.strip().lower()
    m = re.match(r"^([a-z]{2})([a-z].+)$", t)
    if m and m.group(1) in ISO_PREFIX_TO_COUNTRY:
        return ISO_PREFIX_TO_COUNTRY[m.group(1)]
    m = re.match(r"^([a-z]{2})(?=united states)", t)
    if m:
        return "united states"
    return t


def _normalize_restriction(text: str) -> str:
    t = _strip_iso_prefix(text.strip().lower())
    t = re.sub(r"\s+only$", "", t)
    t = re.sub(r"^only\s+", "", t)
    return t.strip()


def _term_is_foreign_country(term: str) -> bool:
    t = _normalize_restriction(term)
    if not t or _restriction_is_worldwide(t) or _restriction_is_india(t):
        return False
    if t in FOREIGN_LOCK_TERMS:
        return True
    return any(country in t or t in country for country in FOREIGN_LOCK_TERMS if len(country) > 3)


def extract_location_locks_from_text(text: str) -> list[str]:
    """Find 'Germany only', 'only Norway', 'must be based in Brazil', etc."""
    if not text:
        return []
    clean = re.sub(r"\s+", " ", text)
    found: list[str] = []

    for m in re.finditer(r"\b([\w\s\-]{2,45}?)\s+only\b", clean, re.I):
        phrase = m.group(1).strip()
        low = phrase.lower()
        if any(low == s or low.endswith(" " + s) for s in ONLY_PHRASE_SKIP):
            continue
        if _term_is_foreign_country(phrase) or re.search(r"\bonly\b", m.group(0), re.I):
            if _term_is_foreign_country(phrase):
                found.append(phrase)

    for m in re.finditer(
        r"\bonly\s+([\w\s\-]{2,45}?)(?:\s+candidates|\s+residents|\.|,|$)",
        clean,
        re.I,
    ):
        phrase = m.group(1).strip()
        if _term_is_foreign_country(phrase):
            found.append(phrase)

    for m in re.finditer(
        r"\b(?:must be|required to be)\s+(?:legally\s+)?(?:located|based|resident|living)\s+in\s+"
        r"([\w\s\-]{2,45}?)(?:\.|,|$|\s+to\s)",
        clean,
        re.I,
    ):
        phrase = m.group(1).strip()
        if _term_is_foreign_country(phrase):
            found.append(phrase)

    seen: set[str] = set()
    out: list[str] = []
    for item in found:
        key = _normalize_restriction(item)
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
    return out


def get_location_restrictions(job: Any) -> list[str]:
    restrictions: list[str] = []
    loc = getattr(job, "location", "") or ""
    title = getattr(job, "title", "") or ""
    desc = getattr(job, "raw_description", "") or ""
    meta = getattr(job, "parsed_metadata", None) or {}
    if isinstance(meta, dict):
        for key in ("location_restrictions", "locationRestrictions", "candidate_required_location"):
            val = meta.get(key)
            if isinstance(val, list):
                restrictions.extend(str(x) for x in val if x)
            elif isinstance(val, str) and val.strip():
                restrictions.append(val.strip())
    if loc.strip():
        for part in re.split(r"[,;|/]", loc):
            part = part.strip()
            if part:
                restrictions.append(part)
    for blob in (title, desc, loc):
        restrictions.extend(extract_location_locks_from_text(blob))
    seen: set[str] = set()
    out: list[str] = []
    for r in restrictions:
        key = _normalize_restriction(r)
        if key and key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _job_text(job: Any) -> str:
    title = getattr(job, "title", "") or ""
    desc = getattr(job, "raw_description", "") or ""
    loc = getattr(job, "location", "") or ""
    meta = getattr(job, "parsed_metadata", None) or {}
    if isinstance(meta, dict):
        for key in ("location_restrictions", "locationRestrictions", "candidate_required_location"):
            val = meta.get(key)
            if isinstance(val, list):
                loc += " " + " ".join(str(v) for v in val)
            elif isinstance(val, str):
                loc += " " + val
    return f"{title} {desc} {loc}"


def _mentions_india(text: str) -> bool:
    return any(p.search(text) for p in INDIA_ONSITE_PATTERNS)


def _restriction_is_worldwide(text: str) -> bool:
    t = _normalize_restriction(text)
    return any(m in t for m in WORLDWIDE_MARKERS)


def _restriction_is_india(text: str) -> bool:
    return any(p.search(_normalize_restriction(text)) for p in INDIA_ONSITE_PATTERNS)


def _restriction_is_foreign_lock(text: str) -> bool:
    t = _normalize_restriction(text)
    if not t or _restriction_is_worldwide(t) or _restriction_is_india(t):
        return False
    if re.search(r"\bonly\b", text.lower()):
        return _term_is_foreign_country(re.sub(r"\s+only$", "", t, flags=re.I))
    return _term_is_foreign_country(t)


def restrictions_lock_to_foreign_only(restrictions: list[str]) -> bool:
    if not restrictions:
        return False
    if any(_restriction_is_worldwide(r) for r in restrictions):
        return False
    if any(_restriction_is_india(r) for r in restrictions):
        return False
    foreign = [r for r in restrictions if _restriction_is_foreign_lock(r)]
    return len(foreign) > 0


def offers_visa_sponsorship(text: str, job: Any) -> bool:
    text_l = text.lower()
    for pat in NEGATIVE_SPONSOR_PATTERNS:
        if pat.search(text_l):
            return False
    meta = getattr(job, "parsed_metadata", None) or {}
    if isinstance(meta, dict) and meta.get("visa_sponsorship") is True:
        return True
    if getattr(job, "offers_sponsorship", None) is True:
        if any(pat.search(text_l) for pat in POSITIVE_SPONSOR_PATTERNS):
            return True
        return False
    return any(pat.search(text_l) for pat in POSITIVE_SPONSOR_PATTERNS)


def _country_locked(text: str) -> bool:
    locks = extract_location_locks_from_text(text)
    if restrictions_lock_to_foreign_only(locks):
        return True
    text_l = text.lower()
    for pat in COUNTRY_LOCK_PATTERNS:
        m = pat.search(text_l)
        if not m:
            continue
        fragment = m.group(0)
        if extract_location_locks_from_text(fragment):
            return True
    return False


def _remote_proven_eligible(text: str, restrictions: list[str]) -> bool | None:
    """True=global OK, False=country locked, None=unknown."""
    if restrictions_lock_to_foreign_only(restrictions):
        return False
    if any(_restriction_is_worldwide(r) for r in restrictions):
        return True
    if _mentions_india(text):
        return True
    if any(m in text.lower() for m in WORLDWIDE_MARKERS):
        return True
    if _country_locked(text):
        return False
    if restrictions:
        return True
    return None


def is_location_eligible(
    job: Any,
    profile: dict[str, Any] | None = None,
    prefs: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    profile = profile or {}
    js = profile.get("job_search") or build_job_search_block(profile)
    requires_sponsor = js.get(
        "requires_sponsorship",
        (profile.get("work_authorization") or {}).get("requires_sponsorship", True),
    )
    preferred = [c.lower() for c in js.get("preferred_cities") or ["india"]]
    text = _job_text(job)
    text_l = text.lower()
    restrictions = get_location_restrictions(job)
    source = (getattr(job, "source", "") or "").lower()
    is_remote = bool(getattr(job, "is_remote", False)) or "remote" in text_l
    has_sponsor = offers_visa_sponsorship(text, job)
    foreign_locked = restrictions_lock_to_foreign_only(restrictions)

    if source == "adzuna_in" or _mentions_india(text_l):
        return True, ""
    if source == "jsearch" and _mentions_india(text_l):
        return True, ""

    for city in preferred:
        if city in text_l:
            return True, ""

    if js.get("fresher_mode") or (prefs or {}).get("fresher_mode"):
        for pat in SENIOR_YOE_PATTERNS:
            if pat.search(text_l):
                return False, "senior_yoe_required"

    if foreign_locked and not has_sponsor:
        return False, "foreign_country_only"

    if _country_locked(text) and not has_sponsor:
        return False, "country_restricted"

    if is_remote:
        proven = _remote_proven_eligible(text_l, restrictions)
        if proven is False:
            return False, "remote_country_locked"
        if proven is True:
            return True, ""
        if has_sponsor:
            return True, ""
        if requires_sponsor and source in GLOBAL_REMOTE_SOURCES:
            meta = getattr(job, "parsed_metadata", None) or {}
            if isinstance(meta, dict) and meta.get("location_enriched_from_apply_page"):
                return False, "remote_location_unverified"
            return False, "remote_location_unverified"
        if requires_sponsor:
            return False, "remote_requires_sponsor_unknown"
        return True, ""

    if has_sponsor:
        return True, ""

    if not requires_sponsor and _mentions_india(text_l):
        return True, ""

    if requires_sponsor and not _mentions_india(text_l):
        return False, "onsite_abroad_no_sponsor"

    return False, "location_not_eligible"


def infer_offers_sponsorship(text: str, meta: dict | None = None) -> bool | None:
    meta = meta or {}

    class _Probe:
        parsed_metadata = meta
        offers_sponsorship = None

    if offers_visa_sponsorship(text, _Probe()):
        return True
    text_l = text.lower()
    if any(p.search(text_l) for p in NEGATIVE_SPONSOR_PATTERNS):
        return False
    return None


def merge_apply_page_restrictions(
    *,
    location: str | None,
    metadata: dict,
    apply_page_text: str,
) -> tuple[str | None, dict]:
    """Merge country locks scraped from the apply/listing page."""
    locks = extract_location_locks_from_text(apply_page_text)
    if not locks:
        return location, metadata
    meta = dict(metadata)
    existing = list(meta.get("location_restrictions") or [])
    merged = list(dict.fromkeys([*existing, *locks]))
    meta["location_restrictions"] = merged
    meta["location_enriched_from_apply_page"] = True
    loc = location or " ".join(merged)
    if locks and not location:
        loc = " ".join(merged)[:240]
    elif locks:
        loc = f"{location} {' '.join(locks)}"[:240]
    return loc, meta
