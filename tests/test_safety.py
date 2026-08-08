from job_os.core.safety import SafetyValidator
from job_os.schemas.jobs import JobIngest


def test_hard_reject_us_citizen():
    validator = SafetyValidator()
    job = JobIngest(
        external_id="1",
        source="test",
        title="Software Engineer",
        url="https://example.com/job/1",
        raw_description="Must be a US citizen only. No sponsorship.",
    )
    verdict = validator.check_job_eligibility_hard(job)
    assert not verdict.allowed
    assert any("hard_reject" in v for v in verdict.violations)


def test_hard_reject_clearance():
    validator = SafetyValidator()
    job = JobIngest(
        external_id="2",
        source="test",
        title="Engineer",
        url="https://example.com/job/2",
        raw_description="Active security clearance required.",
    )
    verdict = validator.check_job_eligibility_hard(job)
    assert not verdict.allowed


def test_allowed_job():
    validator = SafetyValidator()
    job = JobIngest(
        external_id="3",
        source="test",
        title="Junior Backend Engineer",
        url="https://example.com/job/3",
        raw_description="Remote. Visa sponsorship available. Entry level.",
    )
    verdict = validator.check_job_eligibility_hard(job)
    assert verdict.allowed
