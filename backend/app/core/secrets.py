"""Secret encryption at rest for user-supplied deploy tokens.

Values are stored as ``enc:<fernet token>`` in the user settings JSON so a
DB leak doesn't expose live GitHub PATs. Legacy plaintext values still read
fine, period.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_PREFIX = "enc:"


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.JWT_SECRET_KEY.encode()).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    if value.startswith(_PREFIX):
        return value
    return _PREFIX + _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    if not value.startswith(_PREFIX):
        return value  # legacy plaintext
    try:
        return _fernet().decrypt(value[len(_PREFIX) :].encode()).decode()
    except InvalidToken:
        return value
