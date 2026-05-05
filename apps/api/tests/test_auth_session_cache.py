from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sibyl.auth.session_cache import AccessSessionCache
from sibyl_core.auth import AuthSession


def _session(*, expires_at: datetime, refresh_expires_at: datetime | None = None) -> AuthSession:
    return AuthSession(
        id=uuid4(),
        user_id=uuid4(),
        organization_id=uuid4(),
        expires_at=expires_at,
        refresh_token_expires_at=refresh_expires_at,
    )


def test_access_session_cache_stores_active_session_until_refresh_expiry() -> None:
    now = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    session = _session(
        expires_at=now + timedelta(minutes=5),
        refresh_expires_at=now + timedelta(days=30),
    )
    cache = AccessSessionCache()

    cache.store_session(session, now=now)

    assert cache.get(session.id, now=now + timedelta(days=29)) is True
    assert cache.get(session.id, now=now + timedelta(days=31)) is None


def test_access_session_cache_marks_session_revoked() -> None:
    now = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    session = _session(
        expires_at=now + timedelta(minutes=5),
        refresh_expires_at=now + timedelta(days=30),
    )
    cache = AccessSessionCache()
    cache.store_session(session, now=now)

    cache.mark_revoked(session.id, now=now + timedelta(minutes=1))

    assert cache.get(session.id, now=now + timedelta(minutes=2)) is False


def test_access_session_cache_invalidates_user_sessions() -> None:
    now = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    first = _session(expires_at=now + timedelta(minutes=5))
    second = AuthSession(
        id=uuid4(),
        user_id=first.user_id,
        organization_id=uuid4(),
        expires_at=now + timedelta(minutes=5),
    )
    other = _session(expires_at=now + timedelta(minutes=5))
    cache = AccessSessionCache()

    cache.store_session(first, now=now)
    cache.store_session(second, now=now)
    cache.store_session(other, now=now)
    cache.invalidate_user(first.user_id)

    assert cache.get(first.id, now=now) is None
    assert cache.get(second.id, now=now) is None
    assert cache.get(other.id, now=now) is True
