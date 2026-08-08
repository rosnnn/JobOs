from job_os.services.resume_ingest import parse_resume_text


SAMPLE_RESUME = """ROSHAN KUMAR JHA
Bengaluru, India | +91-6363493731 | connect.rosn@gmail.com
SUMMARY
Full-stack software engineer building production systems.
TECHNICAL SKILLS
Languages: Python, JavaScript, TypeScript, Java, Dart, SQL
Frontend/Mobile: React, Next.js, Flutter, HTML5, CSS3
WORK EXPERIENCE
Full Stack Engineer — Zetheta Algorithms Jun 2026 – Jul 2026
Built LendSwift and an event-driven notification engine.
Machine Learning Intern — Karunadu Technologies Pvt. Ltd. Feb 2026 – May 2026
Built prediction systems using supervised learning.
Software Development Intern — Visabi Technologies Pvt. Ltd. Oct 2025 – Feb 2026
Built sign-in/sign-up flows in Flutter.
VIRTUAL EXPERIENCE PROGRAMS
JPMorgan Chase & Co. — Software Engineering Job Simulation (Forage) [Certificate] Jul 2026
Completed practical tasks in Kafka and REST APIs.
ACADEMIC PROJECTS
FinSight — AI Personal Finance Platform
React + FastAPI dashboard with LSTM/GRU forecasting.
EDUCATION
B.E. in Computer Science — Sri Krishna Institute of Technology (VTU), Bengaluru Aug 2022 – May 2026
GPA: 8.23 / 10.0
"""


def test_parse_resume_text_extracts_real_employment_entries():
    profile = parse_resume_text(SAMPLE_RESUME)

    assert len(profile["employment"]) == 3
    assert profile["employment"][0]["title"] == "Full Stack Engineer"
    assert profile["employment"][0]["company"] == "Zetheta Algorithms"
    assert profile["employment"][0]["period"] == "Jun 2026 – Jul 2026"
    assert all("Simulation" not in (item.get("company", "") + item.get("title", "")) for item in profile["employment"])


def test_parse_resume_text_splits_education_degree_and_institution():
    profile = parse_resume_text(SAMPLE_RESUME)

    assert profile["education"]["degree"] == "B.E. in Computer Science"
    assert "Sri Krishna Institute of Technology" in profile["education"]["institution"]