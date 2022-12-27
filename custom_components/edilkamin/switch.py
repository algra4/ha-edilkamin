"""Platform for sensor integration."""
from __future__ import annotations

import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from custom_components.edilkamin.api.edilkamin_async_api import EdilkaminAsyncApi, HttpException

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add sensors for passed config_entry in HA."""
    async_api = hass.data[DOMAIN][config_entry.entry_id]

    async_add_devices(
        [
            EdilkaminAirekareSwitch(async_api),
            EdilkaminPowerSwitch(async_api),
            EdilkaminRelaxSwitch(async_api),
            EdilkaminChronoModeSwitch(async_api)
        ]
    )


class EdilkaminAirekareSwitch(SwitchEntity):
    """Representation of a Sensor."""

    def __init__(self, api: EdilkaminAsyncApi):
        """Initialize the sensor."""
        self._state = None
        self.api = api
        self.mac_address = api.get_mac_address()
        self._attr_icon = "mdi:air-filter"

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self.mac_address}_airekare_switch"

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        await self.api.enable_airkare()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.api.disable_airkare()

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            self._state = await self.api.get_airkare_status()
        except HttpException as err:
            _LOGGER.error(str(err))
            return


class EdilkaminPowerSwitch(SwitchEntity):
    """Representation of a Sensor."""

    def __init__(self, api: EdilkaminAsyncApi):
        """Initialize the sensor."""
        self._state = None
        self.api = api
        self.mac_address = api.get_mac_address()

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self.mac_address}_power_switch"

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        await self.api.enable_power()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.api.disable_power()

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            self._state = await self.api.get_power_status()
        except HttpException as err:
            _LOGGER.error(str(err))
            return


class EdilkaminRelaxSwitch(SwitchEntity):
    """Representation of a Sensor."""

    def __init__(self, api: EdilkaminAsyncApi):
        """Initialize the sensor."""
        self._state = None
        self.api = api
        self.mac_address = api.get_mac_address()
        self._attr_icon = "mdi:weather-night"

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self.mac_address}_relax_switch"

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        await self.api.enable_relax()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.api.disable_relax()

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            self._state = await self.api.get_relax_status()
        except HttpException as err:
            _LOGGER.error(str(err))
            return

class EdilkaminChronoModeSwitch(SwitchEntity):
    """Representation of a Sensor."""

    def __init__(self, api: EdilkaminAsyncApi):
        """Initialize the sensor."""
        self._state = None
        self.api = api
        self.mac_address = api.get_mac_address()
        self._attr_icon = "mdi:calendar-clock"

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self.mac_address}_chrono_mode_switch"

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        await self.api.enable_chrono_mode()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.api.disable_chrono_mode()

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            self._state = await self.api.get_chrono_mode_status()
        except HttpException as err:
            _LOGGER.error(str(err))
            return