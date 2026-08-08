import asyncio

from job_os.tasks.celery_app import celery_app


@celery_app.task(name="job_os.tasks.workflows.run_daily_discovery")
def run_daily_discovery() -> dict:
    """Celery sync wrapper around async workflow execution."""

    async def _run() -> dict:
        from job_os.db.session import AsyncSessionLocal
        from job_os.services.workflow_service import WorkflowService

        async with AsyncSessionLocal() as session:
            svc = WorkflowService(session)
            workflow = await svc.create_and_run("daily_discovery")
            await session.commit()
            return {"workflow_id": str(workflow.id), "status": workflow.status}

    return asyncio.run(_run())


@celery_app.task(name="job_os.tasks.workflows.run_discovery_only")
def run_discovery_only() -> dict:
    """Periodic live fetch from job boards (no tailoring)."""

    async def _run() -> dict:
        from job_os.db.session import AsyncSessionLocal
        from job_os.services.job_sync import JobSyncService

        async with AsyncSessionLocal() as session:
            result = await JobSyncService(session).fetch_and_list(recent_days=3, limit=None)
            await session.commit()
            return {
                "workflow_id": result["workflow_id"],
                "status": result["workflow_status"],
                "discovered_count": result["discovered_count"],
                "jobs_for_profile": result["jobs_for_profile"],
            }

    return asyncio.run(_run())


@celery_app.task(name="job_os.tasks.workflows.run_submit_applications")
def run_submit_applications() -> dict:
    async def _run() -> dict:
        from job_os.db.session import AsyncSessionLocal
        from job_os.services.workflow_service import WorkflowService

        async with AsyncSessionLocal() as session:
            svc = WorkflowService(session)
            workflow = await svc.run_submit_applications()
            await session.commit()
            return {"workflow_id": str(workflow.id), "status": workflow.status}

    return asyncio.run(_run())


@celery_app.task(name="job_os.tasks.workflows.run_email_sync")
def run_email_sync() -> dict:
    async def _run() -> dict:
        from job_os.config import get_settings
        from job_os.db.session import AsyncSessionLocal
        from job_os.services.workflow_service import WorkflowService

        settings = get_settings()
        if not settings.email_poll_enabled or not settings.gmail_address:
            return {"skipped": True, "reason": "email_not_configured"}

        async with AsyncSessionLocal() as session:
            svc = WorkflowService(session)
            workflow = await svc.create_and_run("email_sync")
            await session.commit()
            return {"workflow_id": str(workflow.id), "status": workflow.status}

    return asyncio.run(_run())
