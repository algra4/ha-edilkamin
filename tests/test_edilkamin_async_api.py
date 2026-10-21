"""Tests for the async API wrapper token sharing and non-blocking calls."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.edilkamin.api.edilkamin_async_api import EdilkaminAsyncApi

MODULE = "custom_components.edilkamin.api.edilkamin_async_api"
MAC = "AA:BB:CC:DD:EE:FF"


class DummyHass:
    """Minimal hass stub running executor jobs inline."""

    async def async_add_executor_job(self, func, *args, **kwargs):
        return func(*args, **kwargs)


@pytest.mark.asyncio
async def test_get_token_uses_token_provider_instead_of_sign_in():
    """A shared token provider is reused instead of signing in on every call."""
    token_provider = AsyncMock(return_value="shared.jwt")
    api = EdilkaminAsyncApi(
        MAC, "user", "pass", DummyHass(), token_provider=token_provider
    )

    with patch(f"{MODULE}.edilkamin.sign_in") as mock_sign_in:
        token = await api.get_token()

    assert token == "shared.jwt"  # noqa: S105
    token_provider.assert_awaited_once()
    mock_sign_in.assert_not_called()


@pytest.mark.asyncio
async def test_get_token_without_provider_falls_back_to_sign_in():
    """Without a provider (e.g. config flow) the wrapper still signs in."""
    api = EdilkaminAsyncApi(MAC, "user", "pass", DummyHass())

    with patch(f"{MODULE}.edilkamin.sign_in", return_value="fresh.jwt") as mock_sign_in:
        token = await api.get_token()

    assert token == "fresh.jwt"  # noqa: S105
    mock_sign_in.assert_called_once_with("user", "pass")


@pytest.mark.asyncio
async def test_execute_command_awaits_mqtt_command_without_executor():
    """Commands are awaited natively, never dispatched to an executor thread."""
    hass = Mock()
    hass.async_add_executor_job = AsyncMock()
    api = EdilkaminAsyncApi(
        MAC, "user", "pass", hass, token_provider=AsyncMock(return_value="shared.jwt")
    )
    payload = {"name": "power", "value": 1}

    with patch(f"{MODULE}.edilkamin.mqtt_command", new_callable=AsyncMock) as mock_cmd:
        mock_cmd.return_value = "executed"
        result = await api.execute_command(payload)

    assert result == "executed"
    mock_cmd.assert_awaited_once_with("shared.jwt", MAC, payload)
    hass.async_add_executor_job.assert_not_called()


@pytest.mark.asyncio
async def test_get_info_awaits_device_info_without_executor():
    """Reading device info is awaited natively, never via an executor thread."""
    hass = Mock()
    hass.async_add_executor_job = AsyncMock()
    api = EdilkaminAsyncApi(
        MAC, "user", "pass", hass, token_provider=AsyncMock(return_value="shared.jwt")
    )

    with patch(f"{MODULE}.edilkamin.device_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = {"nvm": {}}
        result = await api.get_info()

    assert result == {"nvm": {}}
    mock_info.assert_awaited_once_with("shared.jwt", MAC)
    hass.async_add_executor_job.assert_not_called()
