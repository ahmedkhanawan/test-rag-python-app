import logging

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.ratelimit import FailureLimiter
from app.core.security import AuthNotConfiguredError, authenticate_admin, create_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# Per-process limiter for failed logins, keyed by client IP (uvicorn's proxy-headers
# support makes that the real client behind the nginx container).
login_limiter = FailureLimiter()


class LoginRequest(BaseModel):
    username: str = Field(max_length=255)
    password: str = Field(max_length=1024)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request) -> TokenResponse:
    settings = get_settings()
    window = settings.login_window_seconds
    client_ip = request.client.host if request.client else "unknown"

    wait = login_limiter.retry_after(client_ip, settings.login_max_failures, window)
    if wait:
        logger.warning("Login throttled for client %s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(wait)},
        )
    try:
        ok = authenticate_admin(body.username, body.password)
    except AuthNotConfiguredError:
        logger.error("Login attempted but admin authentication is not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on the server.",
        )
    if not ok:
        login_limiter.record_failure(client_ip, window)
        # Neither the attempted username nor password is logged.
        logger.warning("Failed admin login from client %s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    login_limiter.reset(client_ip)
    token, expires_in = create_access_token(body.username)
    logger.info("Admin login succeeded from client %s", client_ip)
    return TokenResponse(access_token=token, expires_in=expires_in)
