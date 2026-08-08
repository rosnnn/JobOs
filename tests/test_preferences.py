"""Tests for job preferences matching."""

from types import SimpleNamespace

from job_os.services.preferences_service import PreferencesService


def test_matches_remote_intern():
    svc = PreferencesService()
    job = SimpleNamespace(
        title="Backend Intern",
        raw_description="Remote internship for new grads",
        location="Remote",
        is_remote=True,
        offers_sponsorship=True,
        discovered_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        parsed_metadata={"is_internship": True},
    )
    prefs = {"remote_only": True, "internship": True, "keywords": ["intern"], "recent_days": 30}
    ok, reasons = svc.matches_job(job, prefs)
    assert ok, reasons


def test_rejects_senior():
    svc = PreferencesService()
    job = SimpleNamespace(
        title="Principal Engineer",
        raw_description="10+ years experience required",
        location="US",
        is_remote=False,
        offers_sponsorship=False,
        discovered_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        parsed_metadata={},
    )
    prefs = {"fresher_friendly": True, "experience_level": "recent_graduate_intern", "keywords": []}
    ok, reasons = svc.matches_job(job, prefs)
    assert not ok
    assert "too_senior" in reasons
