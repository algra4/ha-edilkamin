"""The Edilkamin integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr

from custom_components.edilkamin.api.edilkamin_async_api import EdilkaminAsyncApi

from .const import DOMAIN, MAC_ADDRESS, PASSWORD, USERNAME
from .coordinator import EdilkaminCoordinator
from .pellet import InvalidPelletStorageError, PelletEstimate, entry_lock

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

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
    async with entry_lock(hass, entry.entry_id):
        return await _async_setup_entry_locked(hass, entry)


async def _async_setup_entry_locked(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Keep options from using another estimator during startup."""

    mac_address = entry.data[MAC_ADDRESS]
    username = entry.data[USERNAME]
    password = entry.data[PASSWORD]

    coordinator = EdilkaminCoordinator(hass, username, password, mac_address, entry)

    estimate = PelletEstimate(hass, entry.entry_id)
    try:
        await estimate.async_load(entry.options)
    except InvalidPelletStorageError:
        _LOGGER.exception(
            "Pellet estimate storage for entry %s is invalid; restore a backup. "
            "The device integration will run without the estimate",
            entry.entry_id,
        )
    else:
        coordinator.pellet = estimate

    try:
        await coordinator.async_refresh()
        hass.data[DOMAIN][entry.entry_id] = EdilkaminAsyncApi(
            mac_address=mac_address,
            username=username,
            password=password,
            hass=hass,
            token_provider=coordinator.refresh_token,
        )
        hass.data[DOMAIN].setdefault("coordinators", {})[entry.entry_id] = coordinator
        register_device(hass, entry, mac_address)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(async_update_options))
    except BaseException:
        # Do not leave a half-published estimator for an options flow to use.
        hass.data[DOMAIN].get("coordinators", {}).pop(entry.entry_id, None)
        hass.data[DOMAIN].pop(entry.entry_id, None)
        await coordinator.async_shutdown()
        if coordinator.pellet is not None:
            await coordinator.pellet.async_flush()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    async with entry_lock(hass, entry.entry_id):
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        if unload_ok:
            coordinator = hass.data[DOMAIN]["coordinators"].pop(entry.entry_id)
            await coordinator.async_shutdown()
            if coordinator.pellet is not None:
                await coordinator.pellet.async_flush()
            hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_update_options(hass, entry):
    """Persist the option boundary before reloading entities."""
    async with entry_lock(hass, entry.entry_id):
        coordinator = hass.data[DOMAIN].get("coordinators", {}).get(entry.entry_id)
        if coordinator is not None and coordinator.pellet is not None:
            await coordinator.pellet.async_configure(entry.options)
    await hass.config_entries.async_reload(entry.entry_id)


def register_device(hass: HomeAssistant, config_entry, mac_address):
    """Register a device in the Home Assistant device registry."""
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("edilkamin", mac_address)},
        manufacturer="Edilkamin",
        name="Edilkamin Stove",
        model="The Mind",
        suggested_area="Living Room",
        connections={(dr.CONNECTION_NETWORK_MAC, mac_address)},
    )
