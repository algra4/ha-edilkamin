from datetime import UTC, datetime, timedelta

import jwt

from custom_components.edilkamin.coordinator import EdilkaminCoordinator


class DummyHass:
    async def async_add_executor_job(self, func, *args, **kwargs):
        return func(*args, **kwargs)

def make_token(exp_offset_sec):
    # Generate a JWT token with a custom expiration time
    payload = {"exp": int((datetime.now(UTC) + timedelta(seconds=exp_offset_sec)).timestamp())}  # noqa: E501
    return jwt.encode(payload, key="secret", algorithm="HS256")

def test_is_token_expired_expired():
    coordinator = EdilkaminCoordinator(DummyHass(), "user", "pass", "mac")
    expired_token = make_token(-10)  # Expired token since 10s
    assert coordinator.is_token_expired(expired_token) is True

def test_is_token_expired_valid():
    coordinator = EdilkaminCoordinator(DummyHass(), "user", "pass", "mac")
    valid_token = make_token(3600)  # Expires in 1h
    assert coordinator.is_token_expired(valid_token) is False

def test_is_token_expired_no_exp():
    coordinator = EdilkaminCoordinator(DummyHass(), "user", "pass", "mac")
    # Token without exp field
    token = jwt.encode({}, key="secret", algorithm="HS256")
    assert coordinator.is_token_expired(token) is True

def test_is_token_expired_invalid():
    coordinator = EdilkaminCoordinator(DummyHass(), "user", "pass", "mac")
    # Undecodable token
    assert coordinator.is_token_expired("not.a.jwt") is True
