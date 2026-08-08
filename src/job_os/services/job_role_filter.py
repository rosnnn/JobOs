"""Strict CS / software-engineering role filter — title-first, not loose description keywords."""

from __future__ import annotations

import html
import re

# Title must match at least one (software engineering roles for recent grad / intern)
_SOFTWARE_TITLE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"\bsoftware\s+(developer|engineer|architect|tester)\b",
        r"\b(full[- ]?stack|backend|front[- ]?end|front end)\s+(developer|engineer)\b",
        r"\b(web|mobile|android|ios)\s+(developer|engineer)\b",
        r"\b(devops|dev\s*ops|sre|site reliability)\s+(engineer)?\b",
        r"\b(data|ml|machine learning)\s+(engineer|scientist)\b",
        r"\bcloud\s+(engineer|architect|developer)\b",
        r"\bplatform\s+engineer\b",
        r"\b(application|systems?)\s+software\s+engineer\b",
        r"\b(graduate|junior|entry[- ]level)\s+(software|engineer|developer)\b",
        r"\bsoftware\s+engineer\b",
        r"\bdeveloper\b.*\b(python|java|javascript|node|react|\.net|typescript|golang|go\b)",
        r"\b(python|java|javascript|node|react|\.net)\s+developer\b",
        r"\b(servicenow|salesforce|sharepoint)\s+developer\b",
        r"\bui\s+developer\b",
        r"\b(sdet|software.{0,12}test|test automation)\s+engineer\b",
        r"\bqa\s+engineer\b",
        r"\bautomation\s+engineer\b",
        r"\bsecurity\s+(engineer|analyst)\b",
        r"\bcyber\s*security\s+(engineer|analyst)\b",
        r"\bembedded\s+(software\s+)?(engineer|developer)\b",
        r"\bfirmware\s+engineer\b",
        r"\b(intern|internship|praktikum|werkstudent).{0,40}\b(software|developer|engineer|devops|data)\b",
        r"\b(software|developer|engineer|devops|data).{0,40}\b(intern|internship|praktikum|werkstudent)\b",
        r"\bengineer\b.*\b(software|cloud|platform|automation)\b",
        r"\bdeveloper\b(?!\s*(relations|advocate|success|experience))",
    )
)

# Reject even if description mentions "software" / "python"
_BLOCKED_TITLE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"\bgame\s+test",
        r"\bsurvey\s+taker",
        r"\bfree\s*cash",
        r"\bmarketing\b",
        r"\bcopywriter\b",
        r"\bcreative\s+designer\b",
        r"\bgraphic\s+design",
        r"\bux\s+designer\b(?!.*developer)",
        r"\bproduct\s+designer\b",
        r"\bmerchandis",
        r"\bbookkeeper\b",
        r"\baccountant\b",
        r"\badministrativ",
        r"\bauxiliar\b",
        r"\boffice\s+(general|assistant)",
        r"\bvirtual\s+assistant\b",
        r"\bhealth\s*&?\s*wellness",
        r"\bwellness\s+coach",
        r"\bvoice\s+actor",
        r"\bfire\s+fighter",
        r"\bestimator\b",
        r"\bkey\s+account\b",
        r"\bsales\s+(representative|manager|executive)\b",
        r"\bcustomer\s+(operations|support|success)\b",
        r"\boperations\s+coordinator\b",
        r"\bpr\s*&?\s*marketing",
        r"\brecruiting\b",
        r"\bpersonalberatung\b",
        r"\belektriker\b",
        r"\belektroniker\b",
        r"\bmechatronik",
        r"\bservicetechniker\b",
        r"\bwerkzeugmaschinen\b",
        r"\bstructural\s+analysis\b",
        r"\bstructural\s+engineer\b",
        r"\bnurse\b",
        r"\bteacher\b",
        r"\btutor\b(?!.*software)",
        r"\bwriter\b(?!.*technical)",
        r"\bcontent\s+(writer|creator)\b",
        r"\bsocial\s+media\b",
        r"\bcommunity\s+manager\b",
        r"\bproject\s+manager\b(?!.*software)",
        r"\bproduct\s+manager\b",
        r"\bengineering\s+manager\b",
        r"\bhead\s+of\s+",
        r"\bvp\s+",
        r"\bvice\s+president\b",
        r"\bdirector\b",
        r"\bphysik\s*&?\s*simulation\b(?!.*software)",
        r"\bentwicklungsingenieur\b(?!.*software)",
        r"\bfounding\s+partner\b",
        r"\binvestment",
        r"\btequila\b",
        r"\binterdisciplinary\b",
        r"\bresearch\s+assistant\b(?!.*software|.*computer|.*data)",
        r"\bbot\s+developer\b.*freelance",
        r"\bwhatsapp\b",
        r"\btelegram\b",
        r"\bdiscord\b",
    )
)

# Non-software "engineer" / "developer" titles
_FALSE_ENGINEER = re.compile(
    r"\b(structural|civil|mechanical|electrical|manufacturing|sales|field|biomedical|"
    r"chemical|aerospace|automotive|hvac|piping|process|quality(?!\s+assurance\s+engineer))\s+engineer\b",
    re.I,
)


def normalize_job_title(title: str) -> str:
    if not title:
        return ""
    t = html.unescape(title)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def is_blocked_job_title(title: str) -> tuple[bool, str]:
    t = normalize_job_title(title).lower()
    if len(t) < 4:
        return True, "title_too_short"
    for pat in _BLOCKED_TITLE_PATTERNS:
        if pat.search(t):
            return True, "blocked_title"
    if _FALSE_ENGINEER.search(t):
        return True, "non_software_engineer"
    # "Lead X" / "Manager" without software role in title
    if re.search(r"\b(lead|senior|staff|principal)\s+", t) and not any(
        p.search(t) for p in _SOFTWARE_TITLE_PATTERNS
    ):
        return True, "senior_or_lead_non_dev"
    if re.search(r"\bmanager\b", t) and not re.search(
        r"\b(engineering manager).{0,30}(software|platform|devops)|"
        r"\b(devops|software|platform|data)\s+manager\b",
        t,
        re.I,
    ):
        return True, "manager_non_dev"
    return False, ""


def is_software_engineering_role(title: str, description: str | None = None) -> tuple[bool, str]:
    """
    Title must look like a CS / software role. Description alone is not enough.
    """
    t = normalize_job_title(title)
    blocked, reason = is_blocked_job_title(t)
    if blocked:
        return False, reason

    tl = t.lower()
    for pat in _SOFTWARE_TITLE_PATTERNS:
        if pat.search(tl):
            return True, ""

    # Narrow fallback: title has developer/engineer but not blocked
    if re.search(r"\b(developer|engineer|programmer|coder)\b", tl):
        if not _FALSE_ENGINEER.search(tl):
            return True, ""

    return False, "title_not_software_role"
