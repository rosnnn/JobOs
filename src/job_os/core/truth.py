"""Structured truth validation — resume/cover letter must match canonical profile."""

import re
from dataclasses import dataclass, field

from job_os.core.safety import SafetyVerdict


@dataclass
class TruthCheckResult:
    valid: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class TruthValidator:
    """Ensures generated content cannot falsify experience, authorization, or skills."""

    SENIORITY_BLOCKLIST = [
        r"\b(?:10|15|20)\+?\s*years?\b",
        r"\bprincipal\s+(?:engineer|architect)\b",
        r"\bstaff\s+engineer\b",
        r"\bdistinguished\s+engineer\b",
        r"\bvp\s+of\s+engineering\b",
        r"\bcto\b",
    ]

    AUTHORIZATION_FALSE_CLAIMS = [
        r"\bus\s+citizen(?:ship)?\b",
        r"\bauthorized\s+to\s+work\s+in\s+the\s+us\s+without\s+sponsorship\b",
        r"\bno\s+sponsorship\s+(?:required|needed)\b",
        r"\bgreen\s+card\s+holder\b",
        r"\bexisting\s+h1b\b",
    ]

    def validate_document(
        self,
        text: str,
        profile: dict,
        *,
        document_type: str = "resume",
    ) -> TruthCheckResult:
        violations: list[str] = []
        warnings: list[str] = []

        lower = text.lower()
        years = int(profile.get("experience_years", 0))

        for phrase in profile.get("never_claim", []):
            if phrase.lower() in lower:
                violations.append(f"never_claim:{phrase[:40]}")

        for pattern in self.AUTHORIZATION_FALSE_CLAIMS:
            if re.search(pattern, lower):
                auth = profile.get("work_authorization", {})
                if auth.get("requires_sponsorship", True):
                    violations.append(f"false_authorization:{pattern}")

        if years < 2:
            for pattern in self.SENIORITY_BLOCKLIST:
                if re.search(pattern, lower, re.I):
                    violations.append(f"experience_inflation:{pattern}")

        claimed_skills = self._extract_claimed_skills(lower, profile)
        allowed = {s.lower() for s in profile.get("skills", [])}
        for skill in claimed_skills:
            if skill not in allowed:
                violations.append(f"unlisted_skill:{skill}")

        employers = profile.get("employment", [])
        allowed_companies = {e.get("company", "").lower() for e in employers if e.get("company")}
        if employers:
            for match in re.finditer(r"at\s+([A-Z][A-Za-z0-9&\s]{2,40})", text):
                company = match.group(1).strip().lower()
                if company and company not in allowed_companies and years == 0:
                    warnings.append(f"unverified_employer:{company}")

        if document_type == "cover_letter" and "sponsorship" not in lower:
            if profile.get("work_authorization", {}).get("requires_sponsorship"):
                warnings.append("cover_letter_missing_sponsorship_note")

        return TruthCheckResult(valid=len(violations) == 0, violations=violations, warnings=warnings)

    def _extract_claimed_skills(self, lower_text: str, profile: dict) -> list[str]:
        """Flag skills emphasized in doc that are not in canonical profile."""
        common_tech = [
            "python", "java", "javascript", "typescript", "react", "node", "go", "rust",
            "kubernetes", "docker", "aws", "gcp", "azure", "sql", "postgresql", "mongodb",
            "machine learning", "pytorch", "tensorflow", "llm", "rag",
        ]
        allowed = {s.lower() for s in profile.get("skills", [])}
        flagged = []
        for tech in common_tech:
            if not re.search(rf"\b{re.escape(tech)}\b", lower_text):
                continue
            if tech not in allowed:
                flagged.append(tech)
        return flagged

    def to_safety_verdict(self, result: TruthCheckResult) -> SafetyVerdict:
        return SafetyVerdict(allowed=result.valid, violations=result.violations)
