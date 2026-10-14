import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.security import AuthNotConfiguredError, authenticate_admin, create_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    try:
        ok = authenticate_admin(body.username, body.password)
    except AuthNotConfiguredError:
        logger.error("Login attempted but admin authentication is not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on the server.",
        )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_in = create_access_token(body.username)
    return TokenResponse(access_token=token, expires_in=expires_in)
