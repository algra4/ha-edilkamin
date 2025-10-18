from unittest.mock import patch

import pytest

from custom_components.edilkamin.coordinator import EdilkaminCoordinator


class DummyHass:
    async def async_add_executor_job(self, func, *args, **kwargs):
        return func(*args, **kwargs)

def fake_sign_in(*_args, **_kwargs):
    return "new_token.jwt"


@pytest.mark.asyncio
@patch("custom_components.edilkamin.coordinator.edilkamin.sign_in",
       side_effect=fake_sign_in)
async def test_refresh_token_none(mock_sign_in):
    coordinator = EdilkaminCoordinator(DummyHass(), "user", "pass", "mac")
    coordinator._token = None
    token = await coordinator.refresh_token()
    assert token == "new_token.jwt"  # noqa: S105
    assert coordinator._token == "new_token.jwt"  # noqa: S105
    mock_sign_in.assert_called_once_with("user", "pass")


@pytest.mark.asyncio
@patch("custom_components.edilkamin.coordinator.edilkamin.sign_in",
       side_effect=fake_sign_in)
@patch("custom_components.edilkamin.coordinator.EdilkaminCoordinator.is_token_expired",
       return_value=True)
async def test_refresh_token_expired(mock_is_expired, mock_sign_in):
    coordinator = EdilkaminCoordinator(DummyHass(), "user", "pass", "mac")
    coordinator._token = "expired.jwt"  # noqa: S105
    token = await coordinator.refresh_token()
    assert token == "new_token.jwt"  # noqa: S105
    assert coordinator._token == "new_token.jwt"  # noqa: S105
    mock_sign_in.assert_called_once_with("user", "pass")
    mock_is_expired.assert_called_once_with("expired.jwt")


@pytest.mark.asyncio
@patch("custom_components.edilkamin.coordinator.edilkamin.sign_in",
       side_effect=fake_sign_in)
@patch("custom_components.edilkamin.coordinator.EdilkaminCoordinator.is_token_expired",
       return_value=False)
async def test_refresh_token_valid(mock_is_expired, mock_sign_in):
    coordinator = EdilkaminCoordinator(DummyHass(), "user", "pass", "mac")
    coordinator._token = "valid.jwt"  # noqa: S105
    token = await coordinator.refresh_token()
    assert token == "valid.jwt"  # noqa: S105
    assert coordinator._token == "valid.jwt"  # noqa: S105
    mock_sign_in.assert_not_called()
    mock_is_expired.assert_called_once_with("valid.jwt")
