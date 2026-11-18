"""Token encryption and security utilities using Fernet (AES-128-CBC + HMAC-SHA256)."""

from cryptography.fernet import Fernet
from src.core.config import settings


def get_fernet(key: str | None = None) -> Fernet:
    """Instantiate a Fernet cipher with the provided or configured key."""
    raw_key = key or settings.ENCRYPTION_KEY
    if isinstance(raw_key, str):
        key_bytes = raw_key.encode("utf-8")
    else:
        key_bytes = raw_key
    return Fernet(key_bytes)


def encrypt_token(plain_token: str, key: str | None = None) -> str:
    """Encrypt a plaintext token string into an encrypted string."""
    if not plain_token:
        return ""
    fernet = get_fernet(key)
    encrypted_bytes = fernet.encrypt(plain_token.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_token(encrypted_token: str, key: str | None = None) -> str:
    """Decrypt an encrypted token back into plaintext."""
    if not encrypted_token:
        return ""
    fernet = get_fernet(key)
    decrypted_bytes = fernet.decrypt(encrypted_token.encode("utf-8"))
    return decrypted_bytes.decode("utf-8")
