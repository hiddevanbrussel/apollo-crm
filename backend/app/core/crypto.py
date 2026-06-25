import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _build_fernet() -> Fernet:
    """Return a Fernet instance.

    Uses ENCRYPTION_KEY when provided, otherwise derives a deterministic key
    from JWT_SECRET so local development works without extra setup.
    """
    key = settings.ENCRYPTION_KEY.strip()
    if key:
        return Fernet(key.encode())
    derived = hashlib.sha256(settings.JWT_SECRET.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


_fernet = _build_fernet()


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string and return a token (base64 text)."""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_value(token: str) -> str:
    """Decrypt a previously encrypted token back into plaintext."""
    try:
        return _fernet.decrypt(token.encode()).decode()
    except InvalidToken as exc:  # pragma: no cover - defensive
        raise ValueError("Could not decrypt value with current ENCRYPTION_KEY") from exc


def mask_api_key(api_key: str | None) -> str | None:
    """Return a masked representation of an API key for safe display/logging."""
    if not api_key:
        return None
    if len(api_key) <= 4:
        return "****"
    return f"{'*' * (len(api_key) - 4)}{api_key[-4:]}"
