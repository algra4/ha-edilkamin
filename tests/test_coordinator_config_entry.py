"""Verify explicit config-entry ownership across supported HA releases."""

import asyncio
from unittest.mock import AsyncMock, Mock

from homeassistant.config_entries import ConfigEntry
import pytest

import custom_components.edilkamin as integration
from custom_components.edilkamin.coordinator import EdilkaminCoordinator


@pytest.mark.parametrize("with_entry", [False, True])
def test_coordinator_keeps_explicit_config_entry(with_entry):
    entry = Mock(spec=ConfigEntry) if with_entry else None
    coordinator = EdilkaminCoordinator(
        Mock(), "user", "unused", "00:11:22:33:44:55", config_entry=entry
    )
    assert coordinator.config_entry is entry


def test_setup_passes_its_entry_to_coordinator(monkeypatch):
    hass = Mock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    entry = Mock(spec=ConfigEntry)
    entry.entry_id = "test-entry"
    entry.data = {
        "username": "user",
        "password": "unused",
        "mac_address": "00:11:22:33:44:55",
    }
    coordinator = Mock(async_refresh=AsyncMock())
    factory = Mock(return_value=coordinator)
    monkeypatch.setattr(integration, "EdilkaminCoordinator", factory)
    monkeypatch.setattr(integration, "EdilkaminAsyncApi", Mock())
    monkeypatch.setattr(integration, "register_device", Mock())

    assert asyncio.run(integration.async_setup_entry(hass, entry))
    factory.assert_called_once_with(
        hass, "user", "unused", "00:11:22:33:44:55", config_entry=entry
    )
    coordinator.async_refresh.assert_awaited_once()
