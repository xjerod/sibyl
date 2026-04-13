"""Password hashing compatibility exports for the API package."""

from sibyl_core.auth.passwords import (
    PasswordError,
    PasswordHash,
    hash_password,
    verify_password,
)

__all__ = ["PasswordError", "PasswordHash", "hash_password", "verify_password"]
