import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from job_os.config import get_settings


class ProfileService:
    """Loads canonical user truth from disk — never invent beyond this."""

    def __init__(self, profile_path: Path | None = None):
        self._path = profile_path or get_settings().user_profile_path

    def load(self) -> dict[str, Any]:
        if not self._path.exists():
            profile = _default_profile()
        else:
            profile = json.loads(self._path.read_text(encoding="utf-8"))

        settings = get_settings()
        if settings.gmail_address:
            profile.setdefault("email", settings.gmail_address)
        if settings.account_signup_password:
            profile["account_password"] = settings.account_signup_password
        profile.setdefault("experience_type", "recent_graduate_internships_only")
        profile.setdefault(
            "screening_answers",
            {
                "requires_sponsorship": "Yes",
                "authorized_to_work_us": "No — require visa sponsorship",
                "years_experience": "1 (internships and apprenticeships)",
                "education_status": "Recent graduate — B.E. Computer Science",
            },
        )
        return profile

    def save(self, profile: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(profile, indent=2), encoding="utf-8")


@lru_cache
def get_profile_service() -> ProfileService:
    return ProfileService()


def _default_profile() -> dict[str, Any]:
    return {
        "full_name": "Candidate",
        "email": "candidate@example.com",
        "experience_years": 0,
        "skills": [],
        "projects": [],
        "never_claim": [],
    }
