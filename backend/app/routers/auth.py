from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)

from app.core.config import settings
from app.core.identity_email import IdentityEmailDeliveryError, send_identity_token
from app.core.logging import logger
from app.dependencies.current_user import (
    AuthContext,
    get_auth_context,
    get_current_user,
)
from app.dependencies.request_context import client_ip
from app.dependencies.user_dependencies import get_user_service
from app.models.user import User
from app.schemas.user import (
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.schemas.user_settings import (
    EmailVerificationRequested,
    PasswordChange,
    PasswordResetConfirmation,
    PasswordResetRequest,
    StatusMessage,
    TokenConfirmation,
)
from app.services.user_service import UserService

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


def deliver_identity_token(email: str, token: str, purpose: str) -> None:
    try:
        send_identity_token(email, token, purpose)
    except IdentityEmailDeliveryError:
        logger.warning("Identity email delivery failed.", extra={"purpose": purpose})


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    user: UserCreate,
    request: Request,
    service: UserService = Depends(get_user_service),
):
    try:
        return service.create_user(user, client_ip(request))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
)
def login(
    credentials: UserLogin,
    request: Request,
    service: UserService = Depends(get_user_service),
):
    try:
        return service.authenticate_user(
            email=credentials.email,
            password=credentials.password,
            ip_address=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    service: UserService = Depends(get_user_service),
):
    service.logout(context.user.id, client_ip(request), context.session.id)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(
    request: Request,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    service.logout(current_user.id, client_ip(request))


@router.post(
    "/verify-email/request",
    response_model=EmailVerificationRequested,
    response_model_exclude_none=True,
)
def request_email_verification(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    response.headers["Cache-Control"] = "no-store"
    token = service.issue_email_verification(current_user.id, client_ip(request))
    if token is not None:
        background_tasks.add_task(
            deliver_identity_token, current_user.email, token, "email_verification"
        )
    return EmailVerificationRequested(
        message="Email verification requested.",
        debug_token=(
            token
            if settings.DEBUG and settings.APP_ENV in {"local", "development", "test"}
            else None
        ),
    )


@router.post("/verify-email/confirm", response_model=StatusMessage)
def confirm_email_verification(
    payload: TokenConfirmation,
    request: Request,
    service: UserService = Depends(get_user_service),
):
    try:
        service.confirm_email_verification(payload.token, client_ip(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StatusMessage(message="Email verified successfully.")


@router.post("/password-reset/request", response_model=StatusMessage)
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    service: UserService = Depends(get_user_service),
):
    response.headers["Cache-Control"] = "no-store"
    token = service.request_password_reset(payload.email, client_ip(request))
    if token is not None:
        background_tasks.add_task(
            deliver_identity_token, payload.email, token, "password_reset"
        )
    return StatusMessage(
        message="If the account exists, password reset instructions will be sent."
    )


@router.post("/password-reset/confirm", response_model=StatusMessage)
def confirm_password_reset(
    payload: PasswordResetConfirmation,
    request: Request,
    service: UserService = Depends(get_user_service),
):
    try:
        service.confirm_password_reset(
            payload.token, payload.new_password, client_ip(request)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StatusMessage(message="Password reset successfully.")


@router.post("/password-change", response_model=StatusMessage)
def change_password(
    payload: PasswordChange,
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    service: UserService = Depends(get_user_service),
):
    try:
        service.change_password(
            context.user,
            context.session,
            payload.current_password,
            payload.new_password,
            client_ip(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StatusMessage(message="Password changed successfully.")
