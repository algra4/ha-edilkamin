"""Offline passive health tests using real HA entities and EntityPlatform."""

from datetime import timedelta
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry,
    device_registry,
    entity_platform,
    entity_registry,
    frame,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest
import pytest_asyncio

from custom_components.edilkamin.api.edilkamin_async_api import EdilkaminAsyncApi
from custom_components.edilkamin.binary_sensor import (
    EdilkaminCheckBinarySensor,
    async_setup_entry,
)
from custom_components.edilkamin.const import DOMAIN
from custom_components.edilkamin.coordinator import EdilkaminCoordinator


@pytest_asyncio.fixture
async def ha(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    frame.async_setup(hass)
    hass.config_entries = ConfigEntries(hass, {})
    await area_registry.async_load(hass)
    await entity_registry.async_load(hass)
    await device_registry.async_load(hass)
    yield hass
    await hass.async_stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_success", [True, False])
async def test_passive_health_lifecycle(ha, initial_success):
    """Initial state, repeated failures, recovery and removal need no I/O."""
    coordinator = EdilkaminCoordinator(ha, "offline", "offline", "test-mac")
    coordinator.last_update_success = initial_success
    entity = EdilkaminCheckBinarySensor(coordinator)
    existing = entity_registry.async_get(ha).async_get_or_create(
        "binary_sensor",
        DOMAIN,
        "test-mac_check_binary_sensor",
        suggested_object_id="existing_stove_check",
    )
    platform = entity_platform.EntityPlatform(
        hass=ha,
        logger=logging.getLogger(__name__),
        domain="binary_sensor",
        platform_name=DOMAIN,
        platform=None,
        scan_interval=timedelta(seconds=30),
        entity_namespace=None,
    )
    with (
        patch.object(EdilkaminAsyncApi, "check", AsyncMock()) as check,
        patch.object(EdilkaminAsyncApi, "execute_command", AsyncMock()) as command,
        patch("edilkamin.sign_in") as sign_in,
        patch("edilkamin.device_info", AsyncMock()) as read,
        patch.object(coordinator, "async_request_refresh", AsyncMock()) as refresh,
    ):
        # Even update_before_add and manual updates must not trigger an API read.
        await platform.async_add_entities([entity], update_before_add=True)
        assert not entity.should_poll
        assert entity.available
        assert entity.device_class == BinarySensorDeviceClass.PROBLEM
        assert entity.entity_category == EntityCategory.DIAGNOSTIC
        assert entity.unique_id == "test-mac_check_binary_sensor"
        assert entity.device_info["identifiers"] == {(DOMAIN, "test-mac")}
        assert entity.name == "Check configuration"
        state = ha.states.get(entity.entity_id)
        assert state.state == ("off" if initial_success else "on")
        assert state.attributes["device_class"] == "problem"
        registry_entry = entity_registry.async_get(ha).async_get(entity.entity_id)
        assert entity.entity_id == existing.entity_id
        assert registry_entry.id == existing.id
        assert registry_entry.unique_id == "test-mac_check_binary_sensor"
        assert registry_entry.entity_category == EntityCategory.DIAGNOSTIC

        for _ in range(2):
            coordinator.async_set_update_error(UpdateFailed("offline test failure"))
            await ha.async_block_till_done()
            assert entity.available
            assert ha.states.get(entity.entity_id).state == "on"

        # No telemetry freshness test is implied: an unchanged payload is enough.
        coordinator.async_set_updated_data({})
        await ha.async_block_till_done()
        assert ha.states.get(entity.entity_id).state == "off"
        await entity.async_update()
        await entity.async_update_ha_state(force_refresh=True)
        assert ha.states.get(entity.entity_id).state == "off"

        await platform.async_reset()
        assert not coordinator._listeners
        # Registered entities remain as HA restored/unavailable placeholders.
        assert ha.states.get(entity.entity_id).state == "unavailable"
        assert ha.states.get(entity.entity_id).attributes["restored"] is True
        await coordinator.async_shutdown()
        for mock in (check, command, sign_in, read, refresh):
            mock.assert_not_called()


@pytest.mark.asyncio
async def test_binary_setup_uses_upstream_coordinator_without_api(ha):
    """Setup uses upstream's single coordinator and needs no command API."""
    coordinator = EdilkaminCoordinator(ha, "offline", "offline", "test-mac")
    coordinator.last_update_success = True
    ha.data[DOMAIN] = {"coordinator": coordinator}
    entities = []
    await async_setup_entry(ha, SimpleNamespace(entry_id="test"), entities.extend)
    assert len(entities) == 2
    check = next(e for e in entities if isinstance(e, EdilkaminCheckBinarySensor))
    assert check.coordinator is coordinator
    assert check.unique_id == "test-mac_check_binary_sensor"
    assert check.is_on is False
    coordinator.async_set_update_error(UpdateFailed("offline test failure"))
    assert check.is_on is True
    await coordinator.async_shutdown()
