from fastapi import APIRouter

from job_os.api import applications, email, events, health, jobs, memory, preferences, profile, strategy, workflows

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(workflows.router)
api_router.include_router(jobs.router)
api_router.include_router(applications.router)
api_router.include_router(preferences.router)
api_router.include_router(email.router)
api_router.include_router(events.router)
api_router.include_router(strategy.router)
api_router.include_router(memory.router)
api_router.include_router(profile.router)
