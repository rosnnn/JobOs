from job_os.browser.form_reasoner import FormReasoner


PROFILE = {
    "full_name": "Roshan Kumar Jha",
    "email": "connect.rosn@gmail.com",
    "phone": "+91-6363493731",
    "location": "Bengaluru, India",
    "linkedin": "https://www.linkedin.com/in/rosnnn",
    "github": "https://github.com/rosnnn",
    "work_authorization": {"requires_sponsorship": True, "willing_to_relocate": True},
    "education": {"institution": "SKIT", "degree": "B.E. CS", "graduation_year": 2026},
    "screening_answers": {"notice_period": "Immediate"},
}


def test_maps_email_and_name():
    reasoner = FormReasoner()
    plan = reasoner.plan(
        dom_fields=[
            {"tag": "INPUT", "type": "email", "name": "email", "id": "email", "label": "Email"},
            {"tag": "INPUT", "type": "text", "name": "first_name", "id": "first_name", "label": "First Name"},
        ],
        profile=PROFILE,
    )
    values = {f.selector_hint: f.value for f in plan.fields}
    assert values.get("email") == PROFILE["email"]
    assert values.get("first_name") == "Roshan"


def test_detects_greenhouse():
    assert FormReasoner().detect_ats("https://boards.greenhouse.io/acme/jobs/123") == "greenhouse"


def test_resume_file_field():
    reasoner = FormReasoner()
    plan = reasoner.plan(
        dom_fields=[
            {"tag": "INPUT", "type": "file", "name": "resume", "id": "resume", "label": "Resume/CV"},
        ],
        profile=PROFILE,
        resume_path="/tmp/resume.pdf",
    )
    assert plan.fields[0].action == "upload"
    assert plan.fields[0].value == "/tmp/resume.pdf"
