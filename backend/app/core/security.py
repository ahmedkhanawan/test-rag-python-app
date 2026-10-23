import hmac
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import MIN_JWT_SECRET_LENGTH, get_settings, reveal

JWT_ALGORITHM = "HS256"

_hasher = PasswordHash((Argon2Hasher(),))
# Verified against when the username is wrong, so timing does not reveal it.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


class AuthNotConfiguredError(RuntimeError):
    """Admin credentials or the JWT secret are missing from the environment."""


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def auth_configured() -> bool:
    s = get_settings()
    secret = reveal(s.jwt_secret)
    return bool(
        s.admin_username
        and reveal(s.admin_password_hash)
        and secret
        and len(secret) >= MIN_JWT_SECRET_LENGTH
    )


def authenticate_admin(username: str, password: str) -> bool:
    """Check credentials against the environment-configured admin account."""
    if not auth_configured():
        raise AuthNotConfiguredError("Authentication is not configured")
    s = get_settings()
    user_ok = hmac.compare_digest(username.encode(), s.admin_username.encode())
    try:
        pw_ok = _hasher.verify(password, reveal(s.admin_password_hash) if user_ok else _DUMMY_HASH)
    except Exception:  # malformed configured hash: fail closed
        pw_ok = False
    return user_ok and pw_ok


def create_access_token(subject: str) -> tuple[str, int]:
    """Return (signed JWT, lifetime in seconds)."""
    s = get_settings()
    lifetime = timedelta(minutes=s.jwt_expire_minutes)
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, reveal(s.jwt_secret), algorithm=JWT_ALGORITHM), int(lifetime.total_seconds())


def decode_access_token(token: str) -> str | None:
    """Return the subject of a valid, unexpired token, else None."""
    s = get_settings()
    if not auth_configured():
        return None
    try:
        payload = jwt.decode(
            token, reveal(s.jwt_secret), algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub"]}
        )
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return sub if sub == s.admin_username else None
