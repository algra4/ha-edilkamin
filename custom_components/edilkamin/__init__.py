"""The Edilkamin integration."""

from __future__ import annotations

import logging

from custom_components.edilkamin.api.edilkamin_async_api import EdilkaminAsyncApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, MAC_ADDRESS, PASSWORD, USERNAME
from .coordinator import EdilkaminCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.SENSOR,
    Platform.SWITCH,
]


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Edilkamin from a config entry."""

    mac_address = entry.data[MAC_ADDRESS]
    username = entry.data[USERNAME]
    password = entry.data[PASSWORD]

    coordinator = EdilkaminCoordinator(hass, username, password, mac_address)

    # First refresh
    await coordinator.async_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = EdilkaminAsyncApi(
        mac_address=mac_address, username=username, password=password, hass=hass
    )
    hass.data[DOMAIN]["coordinator"] = coordinator
    register_device(hass, entry, mac_address)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def register_device(hass: HomeAssistant, config_entry, mac_address):
    """Register a device in the Home Assistant device registry."""
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("edilkamin", mac_address)},
        manufacturer="EdilKamin",
        name="EdilKamin Stove",
        model="The Mind",
        suggested_area="Living Room",
        connections={(dr.CONNECTION_NETWORK_MAC, mac_address)},
    )
