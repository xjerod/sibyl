from sibyl.auth.api_key_common import (
    API_KEY_ARGON2ID_MARKER,
    API_KEY_PBKDF2_ALGORITHM,
    api_key_prefix,
    hash_api_key,
    verify_api_key,
)


def test_api_key_hash_uses_argon2id_by_default() -> None:
    salt, h = hash_api_key("sk_live_test")

    assert salt == API_KEY_ARGON2ID_MARKER
    assert h.startswith("$argon2id$")
    assert verify_api_key("sk_live_test", salt_hex=salt, hash_hex=h) is True
    assert verify_api_key("sk_live_nope", salt_hex=salt, hash_hex=h) is False


def test_api_key_hash_verifies_legacy_pbkdf2_records() -> None:
    salt, h = hash_api_key(
        "sk_live_test",
        salt=b"\x00" * 16,
        iterations=1_000,
        algorithm=API_KEY_PBKDF2_ALGORITHM,
    )

    assert verify_api_key("sk_live_test", salt_hex=salt, hash_hex=h, iterations=1_000) is True
    assert verify_api_key("sk_live_nope", salt_hex=salt, hash_hex=h, iterations=1_000) is False


def test_api_key_hash_rejects_malformed_argon2id_records() -> None:
    assert (
        verify_api_key(
            "sk_live_test",
            salt_hex=API_KEY_ARGON2ID_MARKER,
            hash_hex="not-a-phc-hash",
        )
        is False
    )


def test_api_key_prefix() -> None:
    assert api_key_prefix("abc", length=2) == "ab"
    assert api_key_prefix("abc", length=999) == "abc"
