"""Policy introspection (feature A2): admin \"Permission Preview\"."""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import CurrentUser, require_system_admin
from app.policy.policy_engine import get_policy_engine
from app.schemas.policy import SimulateResponse

router = APIRouter(prefix="/policy", tags=["policy"])


@router.get("/simulate", response_model=SimulateResponse)
def simulate_access(
    role: str = Query(...),
    department: str = Query(...),
    classification: str = Query(...),
    admin: CurrentUser = Depends(require_system_admin),
) -> SimulateResponse:
    """Feature A2 — \"would user X be able to see document Y?\" without logging in as X.
    Same deterministic check the retriever uses; no new logic."""
    policy = get_policy_engine()
    if not policy.valid_classification(classification):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid classification: {classification} (valid: {', '.join(policy.all_classifications())})",
        )
    allowed = policy.simulate_access(role, department, classification)
    return SimulateResponse(
        role=role,
        department=department,
        classification=classification,
        decision="ALLOW" if allowed else "DENY",
    )
