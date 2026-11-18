"""Unit tests for token encryption and decryption utilities."""

import pytest
from cryptography.fernet import Fernet
from src.core.security import decrypt_token, encrypt_token


def test_encrypt_and_decrypt_roundtrip():
    key = Fernet.generate_key().decode("utf-8")
    secret = "secret_access_token_12345"

    encrypted = encrypt_token(secret, key=key)
    assert encrypted != secret
    assert isinstance(encrypted, str)

    decrypted = decrypt_token(encrypted, key=key)
    assert decrypted == secret


def test_empty_token_handling():
    assert encrypt_token("") == ""
    assert decrypt_token("") == ""


def test_invalid_key_fails_decryption():
    key1 = Fernet.generate_key().decode("utf-8")
    key2 = Fernet.generate_key().decode("utf-8")
    secret = "my_token"

    encrypted = encrypt_token(secret, key=key1)
    with pytest.raises(Exception):
        decrypt_token(encrypted, key=key2)
