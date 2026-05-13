"""JWT 签发与校验（不启动应用、不连库）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from auth import AuthTokenExpired, AuthTokenInvalid, create_token, verify_token


@pytest.fixture
def jwt_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    from core import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "JWT_SECRET", "unit-test-jwt-secret-key-32bytes")
    monkeypatch.setattr(settings_mod.settings, "JWT_ALGORITHM", "HS256")
    monkeypatch.setattr(settings_mod.settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 15)


def test_create_verify_roundtrip(jwt_setup: None) -> None:
    assert verify_token(create_token(99)) == 99


def test_verify_expired(jwt_setup: None) -> None:
    t = create_token(1, expires_delta=timedelta(seconds=-1))
    with pytest.raises(AuthTokenExpired):
        verify_token(t)


def test_verify_wrong_secret(jwt_setup: None) -> None:
    from core import settings as settings_mod

    t = create_token(1)
    payload = jwt.decode(
        t,
        settings_mod.settings.JWT_SECRET,
        algorithms=[settings_mod.settings.JWT_ALGORITHM],
    )
    bad = jwt.encode(payload, "wrong-secret-key-thirty-two-bytes-min!!", algorithm="HS256")
    with pytest.raises(AuthTokenInvalid):
        verify_token(bad)


def test_verify_missing_user_id_claim(jwt_setup: None) -> None:
    from core import settings as settings_mod

    exp = datetime.now(timezone.utc) + timedelta(minutes=15)
    t = jwt.encode(
        {"exp": exp},
        settings_mod.settings.JWT_SECRET,
        algorithm=settings_mod.settings.JWT_ALGORITHM,
    )
    with pytest.raises(AuthTokenInvalid):
        verify_token(t)
