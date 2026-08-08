from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from job_os.api.deps import get_session
from job_os.config import get_settings
from job_os.core.events import EventService
from job_os.services.application_data import load_application_defaults, save_application_answers
from job_os.services.credentials_service import CredentialsService
from job_os.services.profile_job_search import build_job_search_block, sync_profile_to_preferences
from job_os.services.profile_service import ProfileService
from job_os.services.resume_ingest import extract_pdf_text, ingest, maybe_refine_profile_with_gemini
from job_os.world_model.service import WorldModelService

router = APIRouter(prefix="/profile", tags=["profile"])


class IngestResumeResponse(BaseModel):
    full_name: str
    email: str
    projects_count: int
    skills_count: int
    profile_path: str
    canonical_path: str
    message: str


class UploadResponse(BaseModel):
    filename: str
    message: str
    full_name: str | None = None


class CredentialsBody(BaseModel):
    gmail_address: str | None = None
    gmail_app_password: str | None = None
    linkedin_email: str | None = None
    linkedin_password: str | None = None
    wellfound_email: str | None = None
    wellfound_password: str | None = None
    gemini_api_key: str | None = None


@router.post("/upload-resume", response_model=IngestResumeResponse)
async def upload_resume(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> IngestResumeResponse:
    settings = get_settings()
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are supported")

    resume_dir = settings.source_resume_dir
    resume_dir.mkdir(parents=True, exist_ok=True)
    dest = resume_dir / file.filename
    content = await file.read()
    dest.write_bytes(content)

    profile = ingest(dest)
    profile = await maybe_refine_profile_with_gemini(extract_pdf_text(dest), profile, dest)
    world = WorldModelService(session)
    await world.merge_update({"user_profile": profile}, reason="api_resume_upload")
    await EventService(session).emit(
        event_type="profile.resume_uploaded",
        source="api.profile",
        payload={
            "filename": file.filename,
            "projects_count": len(profile.get("projects", [])),
            "skills_count": len(profile.get("skills", [])),
        },
    )

    return IngestResumeResponse(
        full_name=profile.get("full_name", ""),
        email=profile.get("email", ""),
        projects_count=len(profile.get("projects", [])),
        skills_count=len(profile.get("skills", [])),
        profile_path=str(settings.user_profile_path),
        canonical_path=str(settings.master_resume_path),
        message=(
            f"Resume parsed from {file.filename}. Job search keywords and board queries "
            "updated from your skills, location, and experience."
        ),
    )


@router.post("/upload-cover-letter", response_model=UploadResponse)
async def upload_cover_letter(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> UploadResponse:
    settings = get_settings()
    cl_dir = settings.cover_letter_upload_path
    cl_dir.mkdir(parents=True, exist_ok=True)
    filename = file.filename or "cover_letter.txt"
    dest = cl_dir / filename
    content = await file.read()
    dest.write_bytes(content)

    profile = ProfileService().load()
    if dest.suffix.lower() in (".txt", ".md"):
        excerpt = content.decode("utf-8", errors="replace").strip()
        profile["cover_letter_excerpt"] = excerpt[:4000]
        if not profile.get("summary"):
            profile["summary"] = excerpt[:600]
    profile["default_cover_letter_path"] = str(dest)
    settings.user_profile_path.parent.mkdir(parents=True, exist_ok=True)
    import json

    settings.user_profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    profile["job_search"] = build_job_search_block(profile)
    sync_profile_to_preferences(profile)
    await EventService(session).emit(
        event_type="profile.cover_letter_uploaded",
        source="api.profile",
        payload={"filename": filename},
    )

    return UploadResponse(
        filename=filename,
        message="Cover letter saved and merged into job-match keywords.",
    )


@router.get("")
async def get_profile() -> dict:
    profile = ProfileService().load()
    if not profile.get("job_search"):
        profile["job_search"] = build_job_search_block(profile)
    return profile


@router.get("/application-answers")
async def get_application_answers() -> dict:
    profile = ProfileService().load()
    return profile.get("application_answers") or load_application_defaults()


@router.put("/application-answers")
async def update_application_answers(body: dict) -> dict:
    saved = save_application_answers(body)
    return {"application_answers": saved, "message": "Application questionnaire saved."}


@router.post("/ingest-resume", response_model=IngestResumeResponse)
async def ingest_resume_endpoint(
    session: AsyncSession = Depends(get_session),
) -> IngestResumeResponse:
    settings = get_settings()
    resume_dir = settings.source_resume_dir
    pdfs = list(resume_dir.glob("*.pdf")) if resume_dir.exists() else []
    if not pdfs:
        raise HTTPException(
            status_code=404,
            detail=f"No PDF in {resume_dir}. Place your resume there and retry.",
        )

    profile = ingest(pdfs[0])
    profile = await maybe_refine_profile_with_gemini(extract_pdf_text(pdfs[0]), profile, pdfs[0])
    world = WorldModelService(session)
    await world.merge_update({"user_profile": profile}, reason="api_resume_ingest")
    await EventService(session).emit(
        event_type="profile.resume_ingested",
        source="api.profile",
        payload={
            "filename": pdfs[0].name,
            "projects_count": len(profile.get("projects", [])),
            "skills_count": len(profile.get("skills", [])),
        },
    )

    return IngestResumeResponse(
        full_name=profile.get("full_name", ""),
        email=profile.get("email", ""),
        projects_count=len(profile.get("projects", [])),
        skills_count=len(profile.get("skills", [])),
        profile_path=str(settings.user_profile_path),
        canonical_path=str(settings.master_resume_path),
        message="Profile ingested. Run POST /workflows with daily_discovery to start.",
    )


@router.get("/credentials")
async def get_credentials() -> dict:
    settings = get_settings()
    creds = CredentialsService().load()

    def _pick(name: str, setting_value: str | None) -> str | None:
        return setting_value or creds.get(name)

    return {
        "gmail_address": _pick("gmail_address", settings.gmail_address),
        "gmail_app_password": creds.get("gmail_app_password") or settings.gmail_app_password,
        "linkedin_email": _pick("linkedin_email", settings.linkedin_email),
        "linkedin_password": creds.get("linkedin_password") or settings.linkedin_password,
        "wellfound_email": _pick("wellfound_email", settings.wellfound_email),
        "wellfound_password": creds.get("wellfound_password") or settings.wellfound_password,
        "gemini_api_key": creds.get("gemini_api_key") or settings.gemini_api_key,
        "masked": {
            "gmail_app_password": CredentialsService.mask(creds.get("gmail_app_password") or settings.gmail_app_password),
            "linkedin_password": CredentialsService.mask(creds.get("linkedin_password") or settings.linkedin_password),
            "wellfound_password": CredentialsService.mask(creds.get("wellfound_password") or settings.wellfound_password),
            "gemini_api_key": CredentialsService.mask(creds.get("gemini_api_key") or settings.gemini_api_key),
        },
    }


@router.put("/credentials")
async def update_credentials(
    body: CredentialsBody,
    session: AsyncSession = Depends(get_session),
) -> dict:
    payload = body.model_dump(exclude_none=True)
    saved = CredentialsService().save(payload)
    await EventService(session).emit(
        event_type="profile.credentials_updated",
        source="api.profile",
        payload={
            "updated_keys": sorted(list(payload.keys())),
        },
    )
    return {
        "message": "Credentials saved locally.",
        "saved": {
            "gmail_address": saved.get("gmail_address"),
            "linkedin_email": saved.get("linkedin_email"),
            "wellfound_email": saved.get("wellfound_email"),
            "gemini_api_key": CredentialsService.mask(saved.get("gemini_api_key")),
        },
    }
