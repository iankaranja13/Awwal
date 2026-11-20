"""Field encryption helper behaviour."""

import pytest
from cryptography.fernet import Fernet

from app.core.crypto import build_fernet, decrypt_json, encrypt_json
from app.core.errors import CryptoError


def test_encrypt_decrypt_json_round_trip(field_encryption_key: str) -> None:
    """Encrypt then decrypt a mapping."""
    payload = {"item": "undescended_testis", "value": True}
    token = encrypt_json(payload, field_encryption_key)
    assert decrypt_json(token, field_encryption_key) == payload


def test_decrypt_rejects_wrong_key(field_encryption_key: str) -> None:
    """Reject decryption with a different key."""
    other_key = Fernet.generate_key().decode("utf-8")
    token = encrypt_json({"a": 1}, field_encryption_key)
    with pytest.raises(CryptoError, match="Failed to decrypt"):
        decrypt_json(token, other_key)


def test_decrypt_rejects_tampered_token(field_encryption_key: str) -> None:
    """Reject a token whose text was modified."""
    token = encrypt_json({"a": 1}, field_encryption_key)
    tampered = ("A" if token[0] != "A" else "B") + token[1:]
    with pytest.raises(CryptoError):
        decrypt_json(tampered, field_encryption_key)


def test_build_fernet_rejects_invalid_key() -> None:
    """Reject key material that is not a Fernet key."""
    with pytest.raises(CryptoError, match="Invalid field encryption key"):
        build_fernet("not-a-fernet-key")


def test_decrypt_rejects_non_mapping_payload(field_encryption_key: str) -> None:
    """Reject a valid token whose JSON is not a mapping."""
    fernet = Fernet(field_encryption_key.encode("utf-8"))
    token = fernet.encrypt(b"[1, 2, 3]").decode("utf-8")
    with pytest.raises(CryptoError, match="not a mapping"):
        decrypt_json(token, field_encryption_key)
