"""Exercise coordinator setup and timeout across supported HA versions."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest

from custom_components.edilkamin.coordinator import EdilkaminCoordinator


def test_coordinator_registers_with_config_entry():
    """The real HA coordinator retains the entry and registers shutdown."""
    entry = Mock()
    coordinator = EdilkaminCoordinator(Mock(), "user", "pass", "mac", entry)
    assert coordinator.config_entry is entry
    entry.async_on_unload.assert_called_once_with(coordinator.async_shutdown)


@pytest.mark.asyncio
async def test_coordinator_update_timeout():
    """A timed-out update becomes an HA UpdateFailed, as before."""
    coordinator = EdilkaminCoordinator(Mock(), "user", "pass", "mac")

    async def slow_update():
        await asyncio.sleep(1)

    coordinator.update_device_information = slow_update
    real_timeout = asyncio.timeout
    with (
        patch(
            "custom_components.edilkamin.coordinator.asyncio.timeout",
            side_effect=lambda _seconds: real_timeout(0.001),
        ),
        pytest.raises(UpdateFailed) as error,
    ):
        await coordinator._async_update_data()
    assert isinstance(error.value.__cause__, TimeoutError)


@pytest.mark.asyncio
async def test_coordinator_update_success():
    """Successful updates still return and store the device data."""
    coordinator = EdilkaminCoordinator(Mock(), "user", "pass", "mac")
    coordinator.update_device_information = AsyncMock(return_value={"status": {}})
    assert await coordinator._async_update_data() == {"status": {}}
    assert coordinator._device_info == {"status": {}}
