from job_os.core.truth import TruthValidator


PROFILE = {
    "full_name": "Test User",
    "experience_years": 0,
    "skills": ["python", "fastapi", "postgresql"],
    "work_authorization": {"requires_sponsorship": True},
    "never_claim": ["US citizenship"],
    "projects": [{"name": "App", "description": "Built API"}],
}


def test_rejects_experience_inflation():
    v = TruthValidator()
    result = v.validate_document("Senior architect with 15 years experience", PROFILE)
    assert not result.valid


def test_rejects_never_claim():
    v = TruthValidator()
    result = v.validate_document("I have US citizenship and can start immediately", PROFILE)
    assert not result.valid


def test_rejects_unlisted_skill():
    v = TruthValidator()
    result = v.validate_document("Expert in rust and kubernetes production systems", PROFILE)
    assert not result.valid
    assert any("unlisted_skill" in x for x in result.violations)


def test_accepts_truthful_resume():
    v = TruthValidator()
    text = "Entry-level developer skilled in python, fastapi, postgresql. Requires visa sponsorship."
    result = v.validate_document(text, PROFILE)
    assert result.valid
