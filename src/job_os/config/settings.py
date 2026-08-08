from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RunMode(str, Enum):
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="JOB_OS_",
        extra="ignore",
    )

    env: str = "development"
    mode: RunMode = RunMode.SUPERVISED
    log_level: str = "INFO"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://jobos:jobos@localhost:5432/jobos"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"

    llm_provider: LLMProvider = LLMProvider.OPENAI
    llm_model: str = "gpt-4o-mini"
    llm_fallback_model: str = "gpt-4o-mini"

    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")

    max_applications_per_day: int = 15
    # 0 = no cap on jobs ingested per discovery run (filtered only by relevancy rules)
    max_jobs_discovered_per_run: int = 0
    max_tailor_per_run: int = 5
    enable_llm_tailoring: bool = True
    require_approval_for_apply: bool = True
    min_delay_between_applications_sec: int = 120

    browser_headless: bool = True
    browser_dry_run: bool = True
    max_browser_apply_per_run: int = 3
    artifact_path: Path = Path("./data/artifacts")

    enabled_sources: str = (
        "jsearch,adzuna_in,adzuna_us,adzuna_gb,adzuna_au,adzuna_ca,adzuna_de,adzuna_sg,"
        "remoteok,remotive,jobicy,arbeitnow,weworkremotely,jobspresso,startup_jobs,findwork,"
        "greenhouse,lever,himalayas,linkedin,wellfound"
    )
    adzuna_app_id: str | None = Field(default=None, validation_alias="ADZUNA_APP_ID")
    adzuna_app_key: str | None = Field(default=None, validation_alias="ADZUNA_APP_KEY")
    # JSearch on RapidAPI — LinkedIn, Indeed, Glassdoor, Naukri, ZipRecruiter via Google for Jobs
    rapidapi_key: str | None = Field(default=None, validation_alias="RAPIDAPI_KEY")
    findwork_api_key: str | None = Field(default=None, validation_alias="FINDWORK_API_KEY")
    himalayas_max_pages: int = 5
    himalayas_max_queries: int = 6
    jsearch_pages_per_query: int = 2
    adzuna_max_pages: int = 10
    browser_board_slow_mo_ms: int = 350
    browser_board_min_delay_ms: int = 900
    browser_board_max_delay_ms: int = 2200
    browser_board_max_scrolls: int = 6
    browser_board_max_queries: int = 8
    browser_board_max_cards_per_query: int = 20
    browser_board_cooldown_minutes: int = 30
    linkedin_email: str | None = Field(default=None, validation_alias="LINKEDIN_EMAIL")
    linkedin_password: str | None = Field(default=None, validation_alias="LINKEDIN_PASSWORD")
    wellfound_email: str | None = Field(default=None, validation_alias="WELLFOUND_EMAIL")
    wellfound_password: str | None = Field(default=None, validation_alias="WELLFOUND_PASSWORD")
    job_retention_days: int = 30
    user_profile_path: Path = Path("./data/user_profile.json")
    master_resume_path: Path = Path("./data/resumes/canonical_base.md")
    source_resume_dir: Path = Path("./resume")
    job_preferences_path: Path = Path("./data/job_preferences.json")
    cover_letter_upload_path: Path = Path("./data/cover_letters")

    # Gmail (use App Password — set in .env, never commit)
    gmail_address: str | None = Field(default=None, validation_alias="GMAIL_ADDRESS")
    gmail_app_password: str | None = Field(default=None, validation_alias="GMAIL_APP_PASSWORD")
    email_poll_enabled: bool = True
    email_poll_interval_sec: int = 300

    # Auto-apply
    auto_apply_max_per_run: int = 10
    auto_approve_on_auto_apply: bool = True
    account_signup_password: str | None = Field(default=None, validation_alias="ACCOUNT_SIGNUP_PASSWORD")

    @property
    def sources_list(self) -> list[str]:
        configured = [s.strip() for s in self.enabled_sources.split(",") if s.strip()]
        required = ["linkedin", "wellfound", "himalayas", "greenhouse", "lever"]
        for src in required:
            if src not in configured:
                configured.append(src)
        return configured

    @property
    def is_supervised(self) -> bool:
        return self.mode == RunMode.SUPERVISED


@lru_cache
def get_settings() -> Settings:
    return Settings()
