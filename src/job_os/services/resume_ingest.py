"""Ingest resume PDF → user_profile.json + canonical markdown base (format-agnostic)."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from pydantic import BaseModel, Field

from job_os.config import LLMProvider, get_settings
from job_os.core.llm import LLMClient
from job_os.services.credentials_service import CredentialsService
from job_os.services.profile_job_search import build_job_search_block, sync_profile_to_preferences

ROOT = Path(__file__).resolve().parents[3]

PRESERVE_ON_REUPLOAD = frozenset(
    {"application_answers", "screening_answers", "account_password"}
)

# Resume section headers → canonical key (matched case-insensitively on a whole line)
SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "headline": ("headline", "professional headline"),
    "summary": (
        "summary",
        "profile",
        "professional summary",
        "career summary",
        "objective",
        "about me",
        "about",
    ),
    "skills": (
        "skills",
        "technical skills",
        "core competencies",
        "core skills",
        "technologies",
        "tech stack",
        "tools",
        "expertise",
    ),
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "work history",
        "career history",
    ),
    "projects": (
        "projects",
        "personal projects",
        "academic projects",
        "key projects",
        "selected projects",
        "project experience",
    ),
    "virtual_experience": (
        "virtual experience",
        "virtual experience programs",
        "job simulations",
        "virtual internships",
    ),
    "education": ("education", "academic background", "qualifications", "academics"),
    "certifications": ("certifications", "certificates", "licenses", "credentials"),
}

# Words that are section labels, not skills
SKILL_NOISE = frozenset(
    {
        "work",
        "experience",
        "education",
        "projects",
        "skills",
        "summary",
        "languages",
        "language",
        "practices",
        "practice",
        "certifications",
        "certification",
        "tools",
        "frameworks",
        "libraries",
        "platforms",
        "other",
        "others",
        "additional",
        "highlights",
    }
)

JOB_TITLE_HINT = re.compile(
    r"\b(intern|developer|engineer|analyst|consultant|manager|designer|architect|specialist|"
    r"coordinator|associate|apprentice|freelance|lead|director|scientist|administrator|"
    r"officer|technician|programmer|tester|qa\b|sre\b|devops)\b",
    re.I,
)
BULLET_ACTION = re.compile(
    r"^(built|designed|wrote|led|improved|collaborated|developed|created|implemented|"
    r"managed|delivered|optimized|automated|stack)\b",
    re.I,
)
TECH_IN_LOCATION = frozenset(
    {"react", "flutter", "python", "node", "java", "sql", "aws", "docker", "kubernetes", "typescript"}
)
MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE_RANGE = rf"(?:{MONTH}\s+)?20\d{{2}}\s*[–\-/]\s*(?:{MONTH}\s+)?(?:20\d{{2}}|Present|Current|Now)"


def _is_plausible_location(text: str) -> bool:
    if "@" in text or "http" in text.lower() or re.search(r"\d{7,}", text):
        return False
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 2:
        return False
    city, region = parts[0], parts[1]
    if city.lower() in TECH_IN_LOCATION or region.lower() in TECH_IN_LOCATION:
        return False
    if not re.match(r"^[A-Za-z][A-Za-z\s.'-]{1,45}$", city):
        return False
    if not re.match(r"^[A-Za-z][A-Za-z\s.'-]{1,45}$", region):
        return False
    return True


def _is_plausible_job_header(title: str, company: str) -> bool:
    if BULLET_ACTION.search(title) or title.lower().startswith("stack"):
        return False
    if re.search(r"\b(simulation|forage|certificate)\b", f"{title} {company}", re.I):
        return False
    if len(title) > 90 or len(company) > 120:
        return False
    if JOB_TITLE_HINT.search(title):
        return True
    if JOB_TITLE_HINT.search(company):
        return False
    return len(title) <= 50 and len(company) <= 80

DEFAULT_NEVER_CLAIM = [
    "US citizenship",
    "security clearance",
    "10+ years experience",
    "existing work authorization without sponsorship",
]


def extract_pdf_text(pdf_path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    raw = "\n".join(page.extract_text() or "" for page in reader.pages)
    return _normalize_resume_text(raw.replace("\uf0b7", " ").replace("\ufffd", "–"))


def _normalize_resume_text(text: str) -> str:
    text = text.replace("\x7f", " ").replace("\uf0b7", " ").replace("\ufffd", "–")
    # UTF-8 em/en dash bytes misread as Windows-1252 (â€" / â€")
    text = text.replace("\u00e2\u20ac\u201d", "—")
    text = text.replace("\u00e2\u20ac\u201c", "–")
    text = re.sub(r"[\u2013\u2212\u2012\u2015]", "–", text)
    return text


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\n", " ")).strip()


def _normalize_header(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().lower().rstrip(":"))


def _header_to_section(line: str) -> str | None:
    key = _normalize_header(line)
    if not key or len(key) > 60:
        return None
    for section, aliases in SECTION_ALIASES.items():
        if key in aliases:
            return section
        compact = key.replace(" ", "")
        if compact in {a.replace(" ", "") for a in aliases}:
            return section
    return None


def extract_sections(text: str) -> dict[str, str]:
    """Split resume into sections by detected header lines."""
    lines = text.splitlines()
    markers: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        section = _header_to_section(line)
        if section:
            markers.append((idx, section))

    sections: dict[str, str] = {}
    if not markers:
        return sections

    for i, (start, name) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(lines)
        body = "\n".join(lines[start + 1 : end]).strip()
        if body:
            prev = sections.get(name, "")
            sections[name] = (prev + "\n" + body).strip() if prev else body
    return sections


def format_person_name(name: str) -> str:
    name = _normalize_space(name)
    if not name:
        return name
    if name == name.upper() and re.search(r"[A-Z]", name):
        return " ".join(part.capitalize() for part in name.split())
    return name


def _split_list_respecting_parens(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in text.replace("\n", ","):
        if char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth = max(0, depth - 1)
            current.append(char)
        elif char in ",;" and depth == 0:
            piece = "".join(current).strip()
            if piece:
                parts.append(piece)
            current = []
        else:
            current.append(char)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _is_valid_skill(token: str) -> bool:
    t = token.strip().strip(".,;|- ")
    if len(t) < 2 or len(t) > 55:
        return False
    if t.endswith(":"):
        return False
    if re.match(r"^[A-Za-z0-9/ \-]+:\s*$", t):
        return False
    low = t.lower()
    if low in SKILL_NOISE:
        return False
    if re.fullmatch(r"(languages?|frontend|backend|mobile|databases?|cloud|practices?|ai\s*/?\s*ml|devops|tools?|frameworks?)\s*:?", low):
        return False
    return True


def _normalize_skill(token: str) -> str:
    return token.strip().strip(".,;|- ")


def _parse_skills_block(block: str) -> list[str]:
    if not block:
        return []
    skills: list[str] = []
    seen: set[str] = set()
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"^[A-Za-z0-9/ \-]+:\s*$", line):
            continue
        line = re.sub(r"^[A-Za-z0-9/ \-]+:\s*", "", line)
        for token in _split_list_respecting_parens(line):
            skill = _normalize_skill(token)
            if not _is_valid_skill(skill):
                continue
            key = skill.lower()
            if key not in seen:
                seen.add(key)
                skills.append(skill)
    return skills


def _parse_skills(text: str, sections: dict[str, str]) -> list[str]:
    block = sections.get("skills", "")
    if not block:
        m = re.search(
            r"(?:TECHNICAL\s*SKILLS|SKILLS|CORE\s*COMPETENCIES)\s*(.+?)(?=\n[A-Z][A-Z\s]{2,}\n|\Z)",
            text,
            re.S | re.I,
        )
        block = m.group(1).strip() if m else ""
    return _parse_skills_block(block)


def _split_trailing_period(text: str) -> tuple[str, str]:
    match = re.match(rf"^(.+?)\s+({DATE_RANGE})$", _normalize_space(text), re.I)
    if not match:
        return text.strip(), ""
    return match.group(1).strip(), match.group(2).strip()


def _looks_like_date_line(line: str) -> bool:
    return bool(re.search(DATE_RANGE, line, re.I) or re.search(r"20\d{2}", line))


def _parse_employment_block(block: str) -> list[dict]:
    if not block:
        return []
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    entries: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        period = ""
        if _looks_like_date_line(line) and entries and not re.search(r"\s*[—–|@]\s*", line):
            entries[-1]["period"] = line
            i += 1
            continue

        # Title — Company (em/en dash only; ASCII hyphen appears in bullet sentences)
        m = re.match(r"^(.+?)\s*[—–]\s*(.+)$", line)
        if m:
            title = m.group(1).strip()
            company = m.group(2).strip()
            company, inline_period = _split_trailing_period(company)
            if _is_plausible_job_header(title, company):
                if inline_period:
                    period = inline_period
                elif i + 1 < len(lines) and _looks_like_date_line(lines[i + 1]):
                    period = lines[i + 1].strip()
                    i += 1
                entries.append({"title": title, "company": company, **({"period": period} if period else {})})
                i += 1
                continue

        # Company | Title (period)
        m = re.match(r"^(.+?)\s*\|\s*(.+?)(?:\s*\(([^)]+)\))?\s*$", line)
        if m:
            entries.append(
                {
                    "company": m.group(1).strip(),
                    "title": m.group(2).strip(),
                    **({"period": m.group(3).strip()} if m.group(3) else {}),
                }
            )
            i += 1
            continue

        # Title at Company
        m = re.match(r"^(.+?)\s+(?:at|@)\s+(.+?)(?:\s*\(([^)]+)\))?\s*$", line, re.I)
        if m:
            entries.append(
                {
                    "title": m.group(1).strip(),
                    "company": m.group(2).strip(),
                    **({"period": m.group(3).strip()} if m.group(3) else {}),
                }
            )
            i += 1
            continue

        i += 1
    return entries[:25]


def _parse_employment(text: str, sections: dict[str, str]) -> list[dict]:
    block = sections.get("experience", "")
    if not block:
        m = re.search(
            r"(?:WORK\s+EXPERIENCE|EXPERIENCE|EMPLOYMENT)\s*(.+?)(?=\n(?:PROJECTS|EDUCATION|SKILLS|CERTIFICATIONS)\b|\Z)",
            text,
            re.S | re.I | re.M,
        )
        block = m.group(1).strip() if m else ""
    return _parse_employment_block(block)


def _technologies_from_context(description: str, known_skills: list[str]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    lower = description.lower()
    for skill in known_skills:
        if skill.lower() in lower:
            key = skill.lower()
            if key not in seen:
                seen.add(key)
                found.append(skill)
    return found[:20]


def _parse_projects_block(block: str, known_skills: list[str]) -> list[dict]:
    if not block:
        return []
    projects: list[dict] = []
    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if not current:
            return
        parts = current.pop("_desc_parts", [])
        desc = _normalize_space(" ".join(parts))
        subtitle = current.pop("subtitle", "")
        if subtitle and subtitle not in desc:
            desc = f"{subtitle}. {desc}".strip() if desc else subtitle
        current["description"] = desc[:2000]
        if current.get("name"):
            projects.append(current)
        current = None

    for raw_line in block.splitlines():
        line = raw_line.strip().lstrip("•-* \t")
        if not line:
            continue

        name_m = re.match(r"^([A-Za-z0-9][A-Za-z0-9\s]{0,78})\s*[—–]\s*(.+)$", line)
        if name_m and not re.match(r"^(stack|tech(?:nologies)?|tools)\s*:", line, re.I):
            flush()
            current = {
                "name": name_m.group(1).strip(),
                "subtitle": _normalize_space(name_m.group(2).strip()),
                "technologies": [],
                "_desc_parts": [],
            }
            continue

        stack_m = re.match(r"^(?:Stack|Tech(?:nologies)?|Tools)\s*:\s*(.+)$", line, re.I)
        if stack_m and current is not None:
            techs = [_normalize_skill(t) for t in _split_list_respecting_parens(stack_m.group(1))]
            current["technologies"] = [t for t in techs if _is_valid_skill(t)]
            continue

        if current is not None:
            current["_desc_parts"].append(line)

    flush()
    for proj in projects:
        if not proj.get("technologies"):
            ctx = f"{proj.get('name', '')} {proj.get('description', '')}"
            proj["technologies"] = _technologies_from_context(ctx, known_skills)
    return projects


def _parse_projects(text: str, sections: dict[str, str], known_skills: list[str]) -> list[dict]:
    block = sections.get("projects", "")
    if not block:
        m = re.search(
            r"(?:PROJECTS|ACADEMIC\s+PROJECTS|PERSONAL\s+PROJECTS)\s*(.+?)(?=\n(?:EDUCATION|CERTIFICATIONS|SKILLS|EXPERIENCE)\b|\Z)",
            text,
            re.S | re.I | re.M,
        )
        block = m.group(1).strip() if m else ""
    return _parse_projects_block(block, known_skills)


def _parse_education_block(block: str) -> dict:
    if not block:
        return {}
    edu: dict = {}
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    if lines:
        first = lines[0]
        m = re.match(r"^(.+?)\s*[—–]\s*(.+)$", first)
        if m and re.search(r"\b(B\.?E\.?|B\.?Tech|B\.?Sc|Bachelor|M\.?S\.?|M\.?Tech|Master|Ph\.?D\.?)\b", m.group(1), re.I):
            institution, _period = _split_trailing_period(m.group(2).strip())
            edu["degree"] = _normalize_space(m.group(1))[:140]
            edu["institution"] = _normalize_space(institution)[:160]
    degree_m = re.search(
        r"(Ph\.?D\.?|M\.?S\.?|M\.?Tech|M\.?Sc|M\.?B\.?A\.?|B\.?E\.?|B\.?Tech|B\.?Sc|Bachelor|Master|Doctor|Associate)[^\n]{0,140}",
        block,
        re.I,
    )
    if degree_m and not edu.get("degree"):
        edu["degree"] = _normalize_space(degree_m.group(0).split("\n")[0])[:140]

    inst_m = re.search(
        r"([A-Za-z0-9][A-Za-z0-9\s&.,'-]{4,100}(?:University|Institute|College|School|Academy)[^\n|]*)",
        block,
        re.I,
    )
    if inst_m and not edu.get("institution"):
        edu["institution"] = _normalize_space(inst_m.group(1).split("|")[0])[:160]

    grad_m = re.search(rf"(20\d{{2}})\s*[–\-/]\s*(20\d{{2}}|Present|Current)", block, re.I)
    if grad_m:
        end = grad_m.group(2)
        edu["graduation_year"] = int(end) if end.isdigit() else None

    gpa_m = re.search(r"(?:GPA|CGPA)[:\s]*([\d.]+(?:/\d+(?:\.\d+)?)?(?:\s*\([^)]+\))?)", block, re.I)
    if gpa_m:
        edu["gpa"] = gpa_m.group(1).strip()
    return edu


class RefinedEmployment(BaseModel):
    title: str
    company: str
    period: str | None = None


class RefinedProject(BaseModel):
    name: str
    description: str = ""
    technologies: list[str] = Field(default_factory=list)


class RefinedEducation(BaseModel):
    degree: str | None = None
    institution: str | None = None
    graduation_year: int | None = None
    gpa: str | None = None


class ResumeRefinement(BaseModel):
    headline: str | None = None
    summary: str | None = None
    employment: list[RefinedEmployment] = Field(default_factory=list)
    projects: list[RefinedProject] = Field(default_factory=list)
    education: RefinedEducation | None = None


def _employment_quality_score(items: list[dict]) -> int:
    score = 0
    for item in items:
        title = str(item.get("title", ""))
        company = str(item.get("company", ""))
        period = str(item.get("period", ""))
        if title:
            score += 2
        if company:
            score += 2
        if period:
            score += 1
        if re.search(DATE_RANGE, company, re.I):
            score -= 3
        if re.search(r"\b(simulation|forage|certificate)\b", f"{title} {company} {period}", re.I):
            score -= 4
    return score


def _needs_llm_refinement(profile: dict) -> bool:
    employment = profile.get("employment") or []
    if len(employment) < 2:
        return True
    if _employment_quality_score(employment) < len(employment) * 3:
        return True
    education = profile.get("education") or {}
    degree = str(education.get("degree", ""))
    institution = str(education.get("institution", ""))
    if degree and institution and institution in degree:
        return True
    return False


def _sanitize_employment_items(items: list[dict]) -> list[dict]:
    out: list[dict] = []
    for item in items:
        title = _normalize_space(str(item.get("title", "")))[:160]
        company = _normalize_space(str(item.get("company", "")))[:160]
        period = _normalize_space(str(item.get("period", "")))[:80]
        if not title or not company:
            continue
        if re.search(r"\b(simulation|forage|certificate)\b", f"{title} {company} {period}", re.I):
            continue
        out.append({"title": title, "company": company, **({"period": period} if period else {})})
    return out[:25]


def _sanitize_project_items(items: list[dict]) -> list[dict]:
    out: list[dict] = []
    for item in items:
        name = _normalize_space(str(item.get("name", "")))[:100]
        if not name:
            continue
        technologies = [_normalize_skill(str(t)) for t in (item.get("technologies") or []) if _is_valid_skill(str(t))]
        out.append(
            {
                "name": name,
                "description": _normalize_space(str(item.get("description", "")))[:2000],
                "technologies": list(dict.fromkeys(technologies))[:20],
            }
        )
    return out[:20]


def _persist_profile_outputs(profile: dict, pdf_path: Path | None = None) -> None:
    profile_path = ROOT / "data" / "user_profile.json"
    profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    sync_profile_to_preferences(profile)

    md = build_canonical_markdown(profile)
    canonical_path = ROOT / "data" / "resumes" / "canonical_base.md"
    canonical_path.write_text(md, encoding="utf-8")

    if pdf_path is not None:
        dest_pdf = ROOT / "data" / "resumes" / "master_resume.pdf"
        if pdf_path.resolve() != dest_pdf.resolve():
            shutil.copy2(pdf_path, dest_pdf)

    identities_path = ROOT / "data" / "identities.json"
    if identities_path.exists():
        identities = json.loads(identities_path.read_text(encoding="utf-8"))
        for item in identities:
            slug = item["slug"]
            role_path = ROOT / "data" / "resumes" / f"{slug}.md"
            role_path.write_text(md, encoding="utf-8")


def _merge_refinement(profile: dict, refined: ResumeRefinement) -> dict:
    merged = dict(profile)
    refined_employment = _sanitize_employment_items([item.model_dump() for item in refined.employment])
    if refined_employment and _employment_quality_score(refined_employment) > _employment_quality_score(profile.get("employment") or []):
        merged["employment"] = refined_employment
        merged["experience_years"] = _estimate_experience_years(refined_employment)
        merged["experience_type"] = _infer_experience_type(refined_employment, merged["experience_years"])

    refined_projects = _sanitize_project_items([item.model_dump() for item in refined.projects])
    if refined_projects and len(refined_projects) >= len(profile.get("projects") or []):
        merged["projects"] = refined_projects

    if refined.education:
        edu = {k: v for k, v in refined.education.model_dump().items() if v not in (None, "")}
        if edu:
            merged["education"] = {**(profile.get("education") or {}), **edu}

    if refined.summary:
        merged["summary"] = _normalize_space(refined.summary)[:2000]
    if refined.headline:
        merged["headline"] = _truncate_at_word(_normalize_space(refined.headline), 160)
    elif merged.get("employment"):
        merged["headline"] = str((merged["employment"] or [{}])[0].get("title", ""))[:160]

    merged["job_search"] = build_job_search_block(merged)
    return merged


async def maybe_refine_profile_with_gemini(text: str, profile: dict, pdf_path: Path | None = None) -> dict:
    settings = get_settings()
    gemini_key = settings.gemini_api_key or CredentialsService().load().get("gemini_api_key")
    if not gemini_key or not _needs_llm_refinement(profile):
        return profile

    llm = LLMClient()
    llm._settings.llm_provider = LLMProvider.GEMINI
    llm._settings.gemini_api_key = gemini_key
    prompt = (
        "Extract a conservative structured resume summary from this text.\n"
        "Rules:\n"
        "- Do not invent employers, titles, dates, or projects.\n"
        "- Keep internships and real work experience in employment.\n"
        "- Exclude virtual job simulations, certificates, and Forage programs from employment.\n"
        "- Split each employment item into title, company, and period.\n"
        "- Keep project names and concise descriptions.\n"
        "- Return JSON only.\n\n"
        f"Resume text:\n{text[:18000]}"
    )
    try:
        refined = await llm.complete_json(
            system="You extract structured, truthful resume data with high precision.",
            user=prompt,
            response_model=ResumeRefinement,
            temperature=0,
        )
    except Exception:
        return profile

    merged = _merge_refinement(profile, refined)
    if merged != profile:
        _persist_profile_outputs(merged, pdf_path)
    return merged


def _parse_education(text: str, sections: dict[str, str]) -> dict:
    block = sections.get("education", "")
    if not block:
        m = re.search(r"EDUCATION\s*(.+?)(?=CERTIFICATIONS|PROJECTS|SKILLS|EXPERIENCE|\Z)", text, re.S | re.I)
        block = m.group(1).strip() if m else ""
    return _parse_education_block(block)


def _split_contact_line(line: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"[|•\u007f\u2022·]+|\s{2,}", line) if p.strip()]
    return parts if parts else [line.strip()]


def _extract_location_from_part(part: str) -> str:
    for loc in re.finditer(
        r"([A-Za-z][A-Za-z\s.'-]{1,45},\s*[A-Za-z][A-Za-z\s.'-]{1,45})",
        part,
    ):
        candidate = _normalize_space(loc.group(1))
        if _is_plausible_location(candidate):
            return candidate
    return ""


def _parse_contact(text: str, lines: list[str]) -> dict:
    contact: dict = {
        "full_name": "",
        "email": "",
        "phone": "",
        "location": "",
        "linkedin": "",
        "github": "",
        "website": "",
    }

    if lines:
        first = lines[0].strip()
        if not re.search(r"@|https?://|linkedin|github|www\.", first, re.I) and len(first.split()) <= 8:
            contact["full_name"] = format_person_name(first)

    for ln in lines[:4]:
        for part in _split_contact_line(ln):
            if not contact["email"]:
                em = re.search(r"[\w.+-]+@[\w.-]+\.\w+", part)
                if em:
                    contact["email"] = em.group(0)
            if not contact["phone"]:
                ph = re.search(r"\+?\d[\d\s().-]{8,18}", part)
                if ph and "@" not in part:
                    contact["phone"] = ph.group(0).strip()
            if not contact["location"]:
                loc = _extract_location_from_part(part)
                if loc and "@" not in part and not re.search(r"linkedin|github", part, re.I):
                    contact["location"] = loc

    if not contact["email"]:
        em = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
        if em:
            contact["email"] = em.group(0)
    if not contact["phone"]:
        ph = re.search(r"\+?\d[\d\s().-]{8,18}", text[:800])
        if ph:
            contact["phone"] = ph.group(0).strip()

    for m in re.finditer(r"linkedin\.com/in/[\w-]+", text, re.I):
        contact["linkedin"] = "https://www." + m.group(0)
        break
    for m in re.finditer(r"github\.com/[\w-]+", text, re.I):
        contact["github"] = "https://" + m.group(0)
        break
    for m in re.finditer(r"https?://[\w.-]+\.(?:dev|io|me|com)/[\w./-]*", text, re.I):
        url = m.group(0)
        if "linkedin" not in url and "github" not in url:
            contact["website"] = url
            break

    return contact


def _parse_summary(sections: dict[str, str]) -> str:
    block = sections.get("summary", "")
    return _normalize_space(block)[:2000] if block else ""


def _first_summary_sentence(summary: str) -> str:
    """First real sentence — ignore dots inside tokens like Node.js or Ph.D."""
    m = re.search(r"^(.+?)\.\s+(?=[A-Z])", summary.strip())
    if m and len(m.group(1).strip()) >= 10:
        return m.group(1).strip()
    return summary.strip().split("\n")[0].strip()


def _truncate_at_word(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rsplit(" ", 1)[0]
    return cut if len(cut) >= 10 else text[:max_len]
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rsplit(" ", 1)[0]
    return cut if len(cut) >= 10 else text[:max_len]


def _parse_headline(sections: dict[str, str], summary: str, employment: list[dict]) -> str:
    if sections.get("headline"):
        return _truncate_at_word(_normalize_space(sections["headline"].split("\n")[0]), 160)
    if summary:
        sentence = _first_summary_sentence(summary)
        if len(sentence) >= 10:
            return _truncate_at_word(sentence, 160)
    if employment:
        return employment[0].get("title", "")[:160]
    return ""


def _parse_work_authorization(text: str, location: str) -> dict:
    low = text.lower()
    home = ""
    if location:
        parts = [p.strip() for p in location.split(",") if p.strip()]
        home = parts[-1] if parts else location.strip()

    requires: bool | None = None
    if re.search(r"require(s)? visa sponsorship|need(s)? sponsorship|sponsorship required", low):
        requires = True
    elif re.search(
        r"authorized to work|eligible to work|permanent resident|no sponsorship required|citizen(ship)?(?:\s+of)?",
        low,
    ):
        requires = False

    willing = bool(re.search(r"relocate|relocation|open to relocate|willing to relocate", low))

    return {
        "current": home,
        "requires_sponsorship": requires if requires is not None else True,
        "willing_to_relocate": willing if willing else True,
    }


def _estimate_experience_years(employment: list[dict]) -> float:
    if not employment:
        return 0.0
    total_months = 0
    for emp in employment:
        period = str(emp.get("period", ""))
        years = re.findall(r"20\d{2}", period)
        if len(years) >= 2:
            total_months += max(1, (int(years[-1]) - int(years[0])) * 12)
        elif len(years) == 1:
            total_months += 6
        else:
            total_months += 4
    return round(min(total_months / 12.0, 40.0), 1) or 0.0


def _infer_experience_type(employment: list[dict], exp_years: float) -> str:
    titles = " ".join(str(e.get("title", "")) for e in employment).lower()
    if re.search(r"\bintern\b|\bapprentice\b|\btrainee\b|\bco-?op\b", titles) or exp_years <= 1.5:
        return "intern / recent graduate"
    if exp_years <= 3:
        return "early career"
    if exp_years <= 8:
        return "mid career"
    return "experienced"


def parse_resume_text(text: str) -> dict:
    """Parse resume PDF text into profile fields — driven by uploaded content only."""
    text = _normalize_resume_text(text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    sections = extract_sections(text)

    contact = _parse_contact(text, lines)
    skills = _parse_skills(text, sections)
    employment = _parse_employment(text, sections)
    summary = _parse_summary(sections)
    projects = _parse_projects(text, sections, skills)
    education = _parse_education(text, sections)
    exp_years = _estimate_experience_years(employment)

    profile: dict = {
        "full_name": contact["full_name"],
        "email": contact["email"],
        "phone": contact["phone"],
        "location": contact["location"],
        "linkedin": contact["linkedin"],
        "github": contact["github"],
        "website": contact.get("website", ""),
        "headline": _parse_headline(sections, summary, employment),
        "summary": summary,
        "experience_years": exp_years,
        "experience_type": _infer_experience_type(employment, exp_years),
        "education": education,
        "work_authorization": _parse_work_authorization(text, contact["location"]),
        "skills": skills,
        "employment": employment,
        "projects": projects,
        "never_claim": list(DEFAULT_NEVER_CLAIM),
    }
    profile["job_search"] = build_job_search_block(profile)
    return profile


def _apply_fresh_resume(parsed: dict, existing: dict | None) -> dict:
    """New upload replaces resume-derived fields; questionnaire/password preserved."""
    fresh = dict(parsed)
    if existing:
        for key in PRESERVE_ON_REUPLOAD:
            if existing.get(key) is not None:
                fresh[key] = existing[key]
        if existing.get("never_claim"):
            fresh["never_claim"] = existing["never_claim"]
    fresh["job_search"] = build_job_search_block(fresh)
    return fresh


def build_canonical_markdown(profile: dict) -> str:
    projects_md = []
    for p in profile.get("projects", []):
        tech = ", ".join(p.get("technologies", []))
        projects_md.append(f"- **{p['name']}**: {p.get('description', '')} ({tech})")

    edu = profile.get("education", {})
    edu_line = f"{edu.get('degree', '')}, {edu.get('institution', '')} ({edu.get('graduation_year', '')})"
    if edu.get("gpa"):
        edu_line += f" — GPA {edu['gpa']}"

    emp_md = []
    for e in profile.get("employment") or []:
        period = f" ({e['period']})" if e.get("period") else ""
        emp_md.append(f"- **{e.get('title', '')}** @ {e.get('company', '')}{period}")

    skills = ", ".join(profile.get("skills", []))
    auth = profile.get("work_authorization", {})
    auth_line = ""
    if auth.get("requires_sponsorship"):
        home = auth.get("current") or profile.get("location") or "home country"
        auth_line = (
            f"Based in {home}; require visa sponsorship for international onsite roles. "
            "Open to eligible locations and worldwide remote where permitted."
        )
    summary = profile.get("summary") or "{{SUMMARY}}"

    return f"""# {profile.get('full_name', '')}
{profile.get('email', '')} | {profile.get('phone', '')} | {profile.get('location', '')}
{profile.get('linkedin', '')} | {profile.get('github', '')}

## Headline
{profile.get('headline', '')}

## Summary
{summary}

## Technical Skills
{skills}

## Experience
{chr(10).join(emp_md) if emp_md else '(See uploaded resume PDF.)'}

## Projects
{chr(10).join(projects_md) if projects_md else '(See uploaded resume PDF.)'}

## Education
{edu_line}

## Work Authorization
{auth_line}
"""


def ingest(pdf_path: Path) -> dict:
    text = extract_pdf_text(pdf_path)
    raw_path = ROOT / "data" / "resumes" / "_extracted_raw.txt"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(text, encoding="utf-8")

    parsed = parse_resume_text(text)
    profile_path = ROOT / "data" / "user_profile.json"
    existing: dict | None = None
    if profile_path.exists():
        existing = json.loads(profile_path.read_text(encoding="utf-8"))
    profile = _apply_fresh_resume(parsed, existing)
    _persist_profile_outputs(profile, pdf_path)

    print(f"Ingested: {profile['full_name']}")
    print(f"  profile -> {profile_path}")
    print(f"  skills: {len(profile.get('skills', []))}, projects: {len(profile.get('projects', []))}")
    return profile


async def sync_world_model() -> None:
    from job_os.db.session import AsyncSessionLocal
    from job_os.services.profile_service import ProfileService
    from job_os.world_model.service import WorldModelService

    profile = ProfileService().load()
    async with AsyncSessionLocal() as session:
        world = WorldModelService(session)
        await world.merge_update({"user_profile": profile}, reason="resume_ingest")
        await session.commit()
    print("  world_model user_profile synced")
