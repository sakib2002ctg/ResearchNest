from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.dependencies.current_user import get_current_user
from app.dependencies.request_context import client_ip
from app.dependencies.user_dependencies import get_user_service
from app.models.user import User
from app.schemas.user import UserResponse
from app.schemas.user_settings import (
    AuditLogResponse,
    DashboardResponse,
    DataExport,
    PreferenceResponse,
    PreferenceUpdate,
    ProfileResponse,
    ProfileUpdate,
    SessionResponse,
)
from app.services.user_service import UserService

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.get("/me/profile", response_model=ProfileResponse)
def get_profile(
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    return service.get_profile(current_user.id)


@router.put("/me/profile", response_model=ProfileResponse)
def update_profile(
    values: ProfileUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    return service.update_profile(
        current_user.id,
        values.model_dump(exclude_unset=True, mode="json"),
        client_ip(request),
    )


@router.get("/me/preferences", response_model=PreferenceResponse)
def get_preferences(
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    return service.get_preferences(current_user.id)


@router.put("/me/preferences", response_model=PreferenceResponse)
def update_preferences(
    values: PreferenceUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    return service.update_preferences(
        current_user.id, values.model_dump(exclude_unset=True), client_ip(request)
    )


@router.get("/me/sessions", response_model=list[SessionResponse])
def sessions(
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    return service.active_sessions(current_user.id)


@router.get("/me/activity", response_model=list[AuditLogResponse])
def activity(
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    return service.activity(current_user.id, limit)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    request: Request,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    service.delete_account(current_user, client_ip(request))


@router.delete("/me/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    if not service.revoke_session_by_id(
        current_user.id, session_id, client_ip(request)
    ):
        raise HTTPException(status_code=404, detail="Session not found.")


@router.get("/me/export", response_model=DataExport)
def export_user_data(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    response.headers["Cache-Control"] = "no-store"
    return service.export_user_data(current_user.id, client_ip(request))


@router.get("/me/dashboard", response_model=DashboardResponse)
def dashboard(
    response: Response,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    response.headers["Cache-Control"] = "no-store"
    return service.dashboard(current_user.id)
