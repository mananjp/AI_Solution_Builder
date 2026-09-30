"""Secret encryption at rest for user-supplied deploy tokens.

Values are stored as ``enc:<fernet token>`` in the user settings JSON so a
DB leak doesn't expose live GitHub PATs. Legacy plaintext values still read
fine, period.

The Fernet key is derived from ``SECRET_ENCRYPTION_KEY``. It used to be derived
from ``JWT_SECRET_KEY``, so a key that arrives with the deployment is also
tried when *decrypting*, letting an existing database migrate itself forward
one secret at a time. New writes always use the primary key, so a rotated
SECRET_ENCRYPTION_KEY re-encrypts the vault lazily on next save.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import settings

_PREFIX = "enc:"


def _key_from(raw: str) -> bytes:
    """Derive a Fernet key from an arbitrary-length passphrase.

    SHA-256 is a KDF here in the loosest sense: it does not stretch, so this
    only has the strength of the passphrase behind it. That is acceptable
    because the value is a high-entropy machine secret, not a human password.
    """
    return base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())


def _fernet() -> MultiFernet:
    """Primary key first, legacy key second.

    `MultiFernet.decrypt` tries each key in turn, which is exactly the
    read-old/write-new behaviour needed to rotate without a migration script.
    """
    keys = []
    if settings.SECRET_ENCRYPTION_KEY:
        keys.append(_key_from(settings.SECRET_ENCRYPTION_KEY))
    if settings.JWT_SECRET_KEY:
        keys.append(_key_from(settings.JWT_SECRET_KEY))
    if not keys:
        raise RuntimeError(
            "No secret-encryption key configured. Set SECRET_ENCRYPTION_KEY to a "
            "high-entropy random string before storing any deploy credentials."
        )
    # Deduplicate: in a fresh deploy both branches may resolve to the same value.
    return MultiFernet([Fernet(k) for k in dict.fromkeys(keys)])


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
