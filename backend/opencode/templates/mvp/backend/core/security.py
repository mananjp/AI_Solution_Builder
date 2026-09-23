from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

try:
    import jwt
    from jwt.exceptions import PyJWTError as JWTError
except (ImportError, ModuleNotFoundError):
    try:
        from jose import JWTError, jwt  # type: ignore[no-redef]
    except (ImportError, ModuleNotFoundError):
        import jwt  # type: ignore[no-redef]

        JWTError = Exception  # type: ignore[assignment,misc]

from passlib.context import CryptContext

from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = settings.JWT_ALGORITHM


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str | uuid.UUID, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        return payload.get("sub")
    except (JWTError, Exception):
        return None
