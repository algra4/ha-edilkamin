"""Tests that the coordinator reads device info without blocking the loop."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.edilkamin.coordinator import EdilkaminCoordinator

MODULE = "custom_components.edilkamin.coordinator"
MAC = "AA:BB:CC:DD:EE:FF"


@pytest.mark.asyncio
@patch(f"{MODULE}.EdilkaminCoordinator.is_token_expired", return_value=False)
@patch(f"{MODULE}.edilkamin.device_info", new_callable=AsyncMock)
async def test_update_device_information_awaits_device_info_without_executor(
    mock_device_info, mock_is_expired
):
    """device_info is awaited natively with the cached token, no executor job."""
    mock_device_info.return_value = {"status": {}}
    hass = Mock()
    hass.async_add_executor_job = AsyncMock()
    coordinator = EdilkaminCoordinator(hass, "user", "pass", MAC)
    coordinator._token = "cached.jwt"  # noqa: S105

    result = await coordinator.update_device_information()

    assert result == {"status": {}}
    mock_device_info.assert_awaited_once_with("cached.jwt", MAC)
    mock_is_expired.assert_called_once_with("cached.jwt")
    hass.async_add_executor_job.assert_not_called()
