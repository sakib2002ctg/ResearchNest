from fastapi import APIRouter, Depends, HTTPException, Request, status

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
from app.services.user_service import UserService

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


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
