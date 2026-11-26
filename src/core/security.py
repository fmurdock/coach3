"""Token encryption and security utilities using Fernet (AES-128-CBC + HMAC-SHA256)."""

import logging
from cryptography.fernet import Fernet, InvalidToken

from src.core.config import settings

logger = logging.getLogger(__name__)


def validate_encryption_key(key: str | None = None) -> bool:
    """Validate that the configured or supplied key is a valid Fernet key."""
    raw_key = key if key is not None else settings.ENCRYPTION_KEY
    if not raw_key:
        return False
    try:
        Fernet(raw_key.encode("utf-8") if isinstance(raw_key, str) else raw_key)
        return True
    except Exception:
        return False


def get_fernet(key: str | None = None) -> Fernet:
    """Instantiate a Fernet cipher with the provided or configured key."""
    raw_key = key or settings.ENCRYPTION_KEY
    key_bytes = raw_key.encode("utf-8") if isinstance(raw_key, str) else raw_key
    return Fernet(key_bytes)


def encrypt_token(plain_token: str, key: str | None = None) -> str:
    """Encrypt a plaintext token string into an encrypted string."""
    if not plain_token:
        return ""
    fernet = get_fernet(key)
    encrypted_bytes = fernet.encrypt(plain_token.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_token(encrypted_token: str, key: str | None = None) -> str:
    """Decrypt an encrypted token back into plaintext (raises InvalidToken on key mismatch)."""
    if not encrypted_token:
        return ""
    fernet = get_fernet(key)
    decrypted_bytes = fernet.decrypt(encrypted_token.encode("utf-8"))
    return decrypted_bytes.decode("utf-8")


def decrypt_token_safe(
    encrypted_token: str | None,
    key: str | None = None,
    context: str = "credential",
) -> tuple[str | None, bool]:
    """Safely decrypt a token, returning (plaintext, decryption_error).

    Never raises InvalidToken so UI/config pages degrade gracefully on key rotation/mismatch.
    """
    if not encrypted_token:
        return None, False
    try:
        return decrypt_token(encrypted_token, key=key), False
    except (InvalidToken, ValueError) as exc:
        logger.warning("Failed to decrypt %s (encryption key mismatch or corrupted ciphertext): %s", context, type(exc).__name__)
        return None, True
