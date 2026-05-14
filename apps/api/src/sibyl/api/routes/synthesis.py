"""Source-grounded synthesis endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException

from sibyl.api.schemas import SynthesisPlanRequest, SynthesisPlanResponse
from sibyl.auth.authorization import ProjectAuthorizationError, verify_entity_project_access
from sibyl.auth.context import AuthContext
from sibyl.auth.dependencies import get_auth_context, get_current_organization, require_org_role
from sibyl.auth.errors import ProjectAccessDeniedError
from sibyl.persistence.auth_runtime import list_accessible_project_graph_ids
from sibyl_core.auth import AuthOrganization, OrganizationRole, ProjectRole
from sibyl_core.models.synthesis import SynthesisRequest, SynthesisSectionRequest
from sibyl_core.services import synthesis as synthesis_service

log = structlog.get_logger()
_READ_ROLES = (
    OrganizationRole.OWNER,
    OrganizationRole.ADMIN,
    OrganizationRole.MEMBER,
    OrganizationRole.VIEWER,
)

router = APIRouter(
    prefix="/synthesis",
    tags=["synthesis"],
    dependencies=[Depends(require_org_role(*_READ_ROLES))],
)


async def _resolve_accessible_synthesis_projects(
    *,
    ctx: AuthContext,
    project: str | None,
) -> set[str] | None:
    if project:
        await verify_entity_project_access(
            None,
            ctx,
            project,
            required_role=ProjectRole.VIEWER,
        )
        return {str(project)}
    accessible_projects = await list_accessible_project_graph_ids(ctx)
    return {str(project_id) for project_id in accessible_projects or set()}


def _core_synthesis_request(request: SynthesisPlanRequest) -> SynthesisRequest:
    return SynthesisRequest(
        goal=request.goal,
        output_type=request.output_type,
        audience=request.audience,
        depth=request.depth,
        seed_query=request.seed_query,
        project=request.project,
        domain=request.domain,
        entity_ids=list(request.entity_ids),
        decision_ids=list(request.decision_ids),
        task_ids=list(request.task_ids),
        artifact_ids=list(request.artifact_ids),
        required_sections=[
            SynthesisSectionRequest(
                title=section.title,
                prompt=section.prompt,
                required_source_ids=list(section.required_source_ids),
            )
            for section in request.required_sections
        ],
        constraints=list(request.constraints),
        max_sections=request.max_sections,
        include_neighborhoods=request.include_neighborhoods,
    )


@router.post("/plan", response_model=SynthesisPlanResponse)
async def plan_synthesis_route(
    request: SynthesisPlanRequest,
    org: AuthOrganization = Depends(get_current_organization),
    ctx: AuthContext = Depends(get_auth_context),
) -> SynthesisPlanResponse:
    """Create a deterministic source-aware synthesis outline."""
    try:
        accessible_projects = await _resolve_accessible_synthesis_projects(
            ctx=ctx,
            project=request.project,
        )
        run = await synthesis_service.plan_synthesis(
            _core_synthesis_request(request),
            organization_id=str(org.id),
            accessible_projects=accessible_projects,
            search_fn=synthesis_service.default_search,
            related_fn=synthesis_service.default_related_sources,
        )
        run = await synthesis_service.materialize_synthesis_section_packs(
            run,
            organization_id=str(org.id),
            principal_id=ctx.user_id,
            accessible_projects=accessible_projects,
            context_fn=synthesis_service.default_context_pack,
        )
        return SynthesisPlanResponse.model_validate(synthesis_service.synthesis_run_to_dict(run))
    except (ProjectAccessDeniedError, ProjectAuthorizationError):
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("synthesis_plan_failed", goal=request.goal, error=str(exc))
        raise HTTPException(
            status_code=500,
            detail="Synthesis planning failed. Please try again.",
        ) from exc
