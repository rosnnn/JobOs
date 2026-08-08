"""Hard safety constraints — no LLM overrides on critical rules."""

from dataclasses import dataclass, field

from job_os.schemas.jobs import JobIngest


REJECT_KEYWORDS_HARD = [
    "us citizen only",
    "us citizenship required",
    "must be a us citizen",
    "security clearance",
    "active clearance",
    "ts/sci",
    "no sponsorship",
    "unable to sponsor",
    "will not sponsor",
    "cannot sponsor",
    "must be authorized to work in the us without sponsorship",
]


@dataclass
class SafetyVerdict:
    allowed: bool
    violations: list[str] = field(default_factory=list)


class SafetyValidator:
    """Rule-based safety checks before any application or content generation."""

    def check_job_eligibility_hard(self, job: JobIngest) -> SafetyVerdict:
        violations: list[str] = []
        text = f"{job.title} {job.raw_description or ''} {job.company_name or ''}".lower()

        for kw in REJECT_KEYWORDS_HARD:
            if kw in text:
                violations.append(f"hard_reject_keyword:{kw}")

        if job.metadata.get("requires_us_citizenship"):
            violations.append("metadata:requires_us_citizenship")
        if job.metadata.get("requires_clearance"):
            violations.append("metadata:requires_clearance")
        if job.metadata.get("no_sponsorship") is True:
            violations.append("metadata:no_sponsorship")

        return SafetyVerdict(allowed=len(violations) == 0, violations=violations)

    def check_application_rate(self, applications_today: int, max_per_day: int) -> SafetyVerdict:
        if applications_today >= max_per_day:
            return SafetyVerdict(
                allowed=False,
                violations=[f"rate_limit:max_{max_per_day}_per_day"],
            )
        return SafetyVerdict(allowed=True)

    def validate_resume_claims(
        self,
        generated_text: str,
        canonical_profile: dict,
    ) -> SafetyVerdict:
        """Phase 1 stub — Phase 2 adds structured diff against canonical profile."""
        violations: list[str] = []
        canonical_years = canonical_profile.get("experience_years", 0)
        inflated_phrases = ["10+ years", "15 years", "senior architect with 20"]
        if canonical_years < 2:
            for phrase in inflated_phrases:
                if phrase.lower() in generated_text.lower():
                    violations.append(f"experience_inflation:{phrase}")
        return SafetyVerdict(allowed=len(violations) == 0, violations=violations)
