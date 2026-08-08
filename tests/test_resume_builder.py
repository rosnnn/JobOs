import asyncio
from uuid import uuid4

from job_os.models.identity import ProfessionalIdentity
from job_os.models.job import Job
from job_os.services.resume_builder import ResumeBuilder  # noqa: E402 — direct import avoids agent registry chain

PROFILE = {
    "full_name": "Roshan Kumar Jha",
    "email": "connect.rosn@gmail.com",
    "phone": "+91-6363493731",
    "location": "Bengaluru, India",
    "experience_years": 1,
    "headline": "Backend Developer",
    "skills": ["Python", "FastAPI", "PostgreSQL", "Redis", "Django", "REST APIs"],
    "education": {"degree": "B.E. CS", "institution": "SKIT", "graduation_year": 2026},
    "work_authorization": {"requires_sponsorship": True},
    "projects": [
        {
            "name": "DocMind",
            "description": "RAG API with FastAPI and vector search",
            "technologies": ["Python", "FastAPI"],
        }
    ],
    "never_claim": [],
}


def test_template_resume_tailoring():
    asyncio.run(_run_template_resume_tailoring())


async def _run_template_resume_tailoring():
    identity = ProfessionalIdentity(
        id=uuid4(),
        slug="backend_engineer",
        display_name="Backend Engineer",
        role_focus="backend python api",
        ats_keywords=["python", "fastapi", "postgresql", "redis"],
        project_emphasis=["api design"],
        base_resume_path="data/resumes/backend_engineer.md",
    )
    job = Job(
        id=uuid4(),
        external_id="1",
        source="test",
        title="Junior Backend Engineer",
        url="https://example.com/job",
        company_name="Acme Corp",
        raw_description="Looking for python fastapi developer remote",
    )
    builder = ResumeBuilder()
    result = await builder.tailor(profile=PROFILE, identity=identity, job=job, use_llm=False)

    assert "Roshan Kumar Jha" in result.content_text
    assert "python" in result.content_text.lower()
    assert "sponsorship" in result.content_text.lower()
    assert "15 years" not in result.content_text.lower()
    assert result.method in ("template", "template_fallback")
