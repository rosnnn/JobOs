"""Generate a reusable global cover letter PDF from user_profile.json."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from job_os.config import get_settings


def build_global_letter(profile: dict) -> str:
    name = profile.get("full_name", "Candidate")
    email = profile.get("email", "")
    phone = profile.get("phone", "")
    linkedin = profile.get("linkedin", "")
    github = profile.get("github", "")
    headline = profile.get("headline", "")
    auth = profile.get("work_authorization") or {}
    edu = profile.get("education") or {}
    degree = (edu.get("degree") or "").strip()
    institution = (edu.get("institution") or "").strip()
    # Institution field sometimes includes graduation date prefix from parser
    institution = re.sub(r"^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\s*[–\-]\s*(?:\w+\s+\d{4}|Present)\s*", "", institution, flags=re.I)
    institution = re.sub(r"^May\s+\d{4}\s+", "", institution, flags=re.I)
    gpa = edu.get("gpa", "")
    edu_line = degree
    if institution:
        edu_line = f"{degree}, {institution}" if degree else institution
    if gpa:
        edu_line += f" (GPA {gpa})"

    emp_lines: list[str] = []
    for e in profile.get("employment") or []:
        title = e.get("title", "")
        company = e.get("company", "")
        period = e.get("period", "")
        if title and company:
            emp_lines.append(f"{title} at {company} ({period})".strip())
    experience = "; ".join(emp_lines[:2]) if emp_lines else "hands-on software internships"

    projects = profile.get("projects") or []
    project_sentences: list[str] = []
    for p in projects[:3]:
        proj_name = p.get("name", "")
        desc = (p.get("description") or "").split(".")[0].strip()
        if proj_name:
            project_sentences.append(f"{proj_name} ({desc})" if desc else proj_name)
    projects_para = "; ".join(project_sentences) if project_sentences else ""

    skills = ", ".join(profile.get("skills", [])[:12])

    sponsorship = ""
    if auth.get("requires_sponsorship"):
        home = auth.get("current") or profile.get("location", "my home country")
        sponsorship = (
            f"I am based in {home} and require visa sponsorship for international onsite roles. "
            "I am fully willing to relocate and committed to contributing long-term where permitted. "
            "I am also open to eligible remote opportunities worldwide.\n\n"
        )

    return f"""Dear Hiring Manager,

I am writing to express my interest in software engineering opportunities at your organization. {headline.rstrip('.')}. I am completing my {edu_line or 'degree'} and am seeking full-time software engineering roles where I can deliver production-quality work from day one.

My recent experience includes {experience}. Across these roles I have worked with modern stacks spanning {skills}, with emphasis on Agile delivery, API design, automated testing, and CI/CD.

Selected work includes: {projects_para}

{sponsorship}I would welcome the opportunity to discuss how my technical skills, published research background, and enthusiasm can support your team's goals. Thank you for your time and consideration.

Sincerely,
{name}
{email} | {phone}
{linkedin} | {github}
""".strip()


def letter_to_html(body: str, name: str) -> str:
    paragraphs = "".join(
        f'<p style="margin:0 0 14px 0;line-height:1.55;">{line.strip()}</p>'
        for line in body.split("\n\n")
        if line.strip()
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ margin: 1in; }}
  body {{
    font-family: Georgia, "Times New Roman", serif;
    font-size: 11.5pt;
    color: #1a1a1a;
    max-width: 7in;
    margin: 0 auto;
  }}
  .sig {{ margin-top: 24px; white-space: pre-line; line-height: 1.45; }}
</style>
</head>
<body>
{paragraphs.replace(name, f"<strong>{name}</strong>", 1) if name in paragraphs else paragraphs}
</body></html>"""


def main() -> None:
    settings = get_settings()
    profile_path = settings.user_profile_path
    if not profile_path.is_absolute():
        profile_path = ROOT / profile_path
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    letter = build_global_letter(profile)
    out_dir = settings.cover_letter_upload_path
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / "global_cover_letter.md"
    pdf_path = out_dir / "global_cover_letter.pdf"
    md_path.write_text(letter, encoding="utf-8")

    name = profile.get("full_name", "")
    html = letter_to_html(letter, name)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            margin={"top": "1in", "bottom": "1in", "left": "1in", "right": "1in"},
            print_background=True,
        )
        browser.close()

    print(f"Cover letter saved:\n  {pdf_path}\n  {md_path}")


if __name__ == "__main__":
    main()
