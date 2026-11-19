"""Application-level encryption for sensitive stored fields."""

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.errors import CryptoError


def build_fernet(key: str) -> Fernet:
    """Build a Fernet instance from settings key material.

    Args:
        key: Raw Fernet key string.

    Returns:
        A Fernet instance ready for encrypt/decrypt calls.

    Raises:
        CryptoError: If the key is not a valid Fernet key.
    """
    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:
        raise CryptoError("Invalid field encryption key.") from exc


def encrypt_json(payload: dict[str, Any], key: str) -> str:
    """Encrypt a JSON-serialisable mapping.

    Args:
        payload: Mapping to encrypt (never logged).
        key: Raw Fernet key string.

    Returns:
        The Fernet token as text.

    Raises:
        CryptoError: If the key is invalid.
    """
    fernet = build_fernet(key)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return fernet.encrypt(raw).decode("utf-8")


def decrypt_json(token: str, key: str) -> dict[str, Any]:
    """Decrypt a token produced by encrypt_json.

    Args:
        token: Fernet token text.
        key: Raw Fernet key string.

    Returns:
        The decrypted mapping.

    Raises:
        CryptoError: If decryption fails or the payload is not a mapping.
    """
    fernet = build_fernet(key)
    try:
        raw = fernet.decrypt(token.encode("utf-8"))
    except (InvalidToken, ValueError) as exc:
        # ValueError covers malformed base64, which is also a bad token.
        raise CryptoError("Failed to decrypt stored data.") from exc
    decoded: Any = json.loads(raw.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise CryptoError("Decrypted payload is not a mapping.")
    return decoded
