"""Human labels for job sources (maps to familiar board names)."""

from job_os.services.job_source_registry import SOURCE_LABELS

BOARD_LABELS: dict[str, str] = dict(SOURCE_LABELS)

EMAIL_BOARD_NOTE = (
    "Job OS pulls from 20+ boards: LinkedIn direct sync, Wellfound direct sync, "
    "JSearch (LinkedIn · Indeed · Glassdoor · Naukri · …), "
    "Adzuna aggregates, RemoteOK, Greenhouse/Lever company ATS, RSS boards, and more. "
    "Set RAPIDAPI_KEY (JSearch) and ADZUNA_APP_ID/KEY in .env for Indeed/Naukri/Glassdoor volume. "
    "Set LINKEDIN_EMAIL/PASSWORD and WELLFOUND_EMAIL/PASSWORD for slow browser-based sync. "
    "LinkedIn/Naukri job-alert emails are also parsed in Inbox when Gmail is connected."
)
