"""Platform for sensor integration."""

from __future__ import annotations

import logging

from custom_components.edilkamin.api.edilkamin_async_api import EdilkaminAsyncApi

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_devices):
    """Add sensors for passed config_entry in HA."""
    async_api = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = hass.data[DOMAIN]["coordinator"]

    async_add_devices(
        [
            EdilkaminAirekareSwitch(async_api, coordinator),
            EdilkaminRelaxSwitch(async_api, coordinator),
            EdilkaminChronoModeSwitch(async_api, coordinator),
        ]
    )


class EdilkaminAirekareSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Sensor."""

    def __init__(self, api: EdilkaminAsyncApi, coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._state = None
        self._api = api
        self._mac_address = api.get_mac_address()
        self._attr_icon = "mdi:air-filter"

        self._attr_device_info = {"identifiers": {("edilkamin", self._mac_address)}}

    @property
    def is_on(self):
        """Return True if the switch sensor is on."""
        return self.coordinator.get_airkare_status()

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self._mac_address}_airekare_switch"

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        await self._api.enable_airkare()
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self._api.disable_airkare()
        await self.coordinator.async_refresh()

class EdilkaminRelaxSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Sensor."""

    def __init__(self, api: EdilkaminAsyncApi, coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._state = None
        self._api = api
        self._mac_address = self.coordinator.get_mac_address()
        self._attr_icon = "mdi:weather-night"

        self._attr_device_info = {"identifiers": {("edilkamin", self._mac_address)}}

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self.coordinator.get_relax_status()

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self._mac_address}_relax_switch"

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        await self._api.enable_relax()
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self._api.disable_relax()
        await self.coordinator.async_refresh()


class EdilkaminChronoModeSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Sensor."""

    def __init__(self, api: EdilkaminAsyncApi, coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._state = None
        self._api = api
        self._mac_address = self.coordinator.get_mac_address()
        self._attr_icon = "mdi:calendar-clock"

        self._attr_device_info = {"identifiers": {("edilkamin", self._mac_address)}}

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self.coordinator.get_chrono_mode_status()

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self._mac_address}_chrono_mode_switch"

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        await self._api.enable_chrono_mode()
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self._api.disable_chrono_mode()
        await self.coordinator.async_refresh()
