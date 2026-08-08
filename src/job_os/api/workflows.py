from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from job_os.api.deps import get_session
from job_os.schemas.workflows import ApprovalDecision, WorkflowCreate, WorkflowResponse, WorkflowStepResponse
from job_os.services.workflow_service import WorkflowService

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("", response_model=WorkflowResponse)
async def create_workflow(
    body: WorkflowCreate,
    session: AsyncSession = Depends(get_session),
) -> WorkflowResponse:
    svc = WorkflowService(session)
    workflow = await svc.create_and_run(body.workflow_type, mode=body.mode, context=body.context)
    return _to_response(workflow)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> WorkflowResponse:
    svc = WorkflowService(session)
    workflow = await svc.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _to_response(workflow)


@router.post("/{workflow_id}/approve", response_model=WorkflowResponse)
async def approve_workflow(
    workflow_id: UUID,
    body: ApprovalDecision,
    session: AsyncSession = Depends(get_session),
) -> WorkflowResponse:
    if not body.approved:
        raise HTTPException(status_code=400, detail="Rejection handling not yet implemented")
    svc = WorkflowService(session)
    workflow = await svc.approve(workflow_id)
    return _to_response(workflow)


def _to_response(workflow) -> WorkflowResponse:
    steps = [
        WorkflowStepResponse(
            id=s.id,
            step_id=s.step_id,
            step_order=s.step_order,
            agent_name=s.agent_name,
            status=s.status,
            output_payload=s.output_payload or {},
        )
        for s in sorted(workflow.steps, key=lambda x: x.step_order)
    ]
    return WorkflowResponse(
        id=workflow.id,
        workflow_type=workflow.workflow_type,
        status=workflow.status,
        mode=workflow.mode,
        correlation_id=workflow.correlation_id,
        context=workflow.context or {},
        started_at=workflow.started_at,
        completed_at=workflow.completed_at,
        error_message=workflow.error_message,
        steps=steps,
    )
