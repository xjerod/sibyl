"""Cryptographic utilities for Sibyl.

Provides encryption/decryption for sensitive values stored in the database,
such as API keys in SystemSettings.

Uses Fernet symmetric encryption with a key derived from SIBYL_SETTINGS_KEY
environment variable. If not set, generates and persists a key on first use.
"""

from __future__ import annotations

import base64
import os
import secrets
from functools import lru_cache
from pathlib import Path

import structlog
from cryptography.fernet import Fernet

log = structlog.get_logger()

# File to persist auto-generated settings key
_SETTINGS_KEY_FILE = Path.home() / ".sibyl" / "settings.key"


def _get_or_create_settings_key() -> bytes:
    """Get encryption key from env var or generate and persist one.

    Priority:
    1. SIBYL_SETTINGS_KEY environment variable
    2. Persisted key in ~/.sibyl/settings.key
    3. Generate new key and persist it

    Returns:
        32-byte key suitable for Fernet.
    """
    # 1. Check environment variable
    env_key = os.environ.get("SIBYL_SETTINGS_KEY", "").strip()
    if env_key:
        # Decode from base64 if it looks like base64
        try:
            if len(env_key) == 44 and env_key.endswith("="):
                return base64.urlsafe_b64decode(env_key)
            # Otherwise treat as raw key (32 bytes hex = 64 chars)
            if len(env_key) == 64:
                return bytes.fromhex(env_key)
            # Fall back to using as-is if 32 bytes
            key_bytes = env_key.encode()
            if len(key_bytes) == 32:
                return key_bytes
            # Hash it if wrong length
            import hashlib

            return hashlib.sha256(key_bytes).digest()
        except Exception:
            # If decoding fails, hash it
            import hashlib

            return hashlib.sha256(env_key.encode()).digest()

    # 2. Check persisted key file
    if _SETTINGS_KEY_FILE.exists():
        try:
            key_data = _SETTINGS_KEY_FILE.read_text().strip()
            return base64.urlsafe_b64decode(key_data)
        except Exception as e:
            log.warning("Failed to read settings key file", error=str(e))

    # 3. Generate new key and persist
    log.info("Generating new settings encryption key", path=str(_SETTINGS_KEY_FILE))
    key = secrets.token_bytes(32)

    try:
        _SETTINGS_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SETTINGS_KEY_FILE.write_text(base64.urlsafe_b64encode(key).decode())
        _SETTINGS_KEY_FILE.chmod(0o600)  # Owner read/write only
    except Exception as e:
        log.warning("Failed to persist settings key", error=str(e))

    return key


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Get cached Fernet instance for encryption/decryption."""
    key = _get_or_create_settings_key()
    # Fernet requires base64-encoded 32-byte key
    fernet_key = base64.urlsafe_b64encode(key)
    return Fernet(fernet_key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string value.

    Args:
        plaintext: The value to encrypt.

    Returns:
        Base64-encoded encrypted ciphertext.
    """
    fernet = _get_fernet()
    ciphertext = fernet.encrypt(plaintext.encode("utf-8"))
    return ciphertext.decode("ascii")


def decrypt_value(ciphertext: str) -> str:
    """Decrypt an encrypted value.

    Args:
        ciphertext: Base64-encoded encrypted value.

    Returns:
        Decrypted plaintext string.

    Raises:
        InvalidToken: If decryption fails (wrong key or corrupted data).
    """
    fernet = _get_fernet()
    plaintext = fernet.decrypt(ciphertext.encode("ascii"))
    return plaintext.decode("utf-8")


def mask_secret(value: str, visible_chars: int = 4) -> str:
    """Mask a secret value for display, showing only last few characters.

    Args:
        value: The secret value to mask.
        visible_chars: Number of characters to show at the end.

    Returns:
        Masked string like "sk-...abc1".
    """
    if not value:
        return ""
    if len(value) <= visible_chars:
        return "*" * len(value)

    # Show prefix if it looks like an API key
    prefix = ""
    if value.startswith("sk-"):
        prefix = "sk-"
        value = value[3:]
    elif value.startswith("sk-ant-"):
        prefix = "sk-ant-"
        value = value[7:]

    visible = value[-visible_chars:]
    return f"{prefix}...{visible}"
