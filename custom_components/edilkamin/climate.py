"""Platform for climate integration."""

from __future__ import annotations

import logging

from custom_components.edilkamin.api.edilkamin_async_api import EdilkaminAsyncApi

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CLIMATE_HVAC_MODE_MANAGED = [HVACMode.HEAT, HVACMode.OFF]

FAN_MODES_MANAGED = ["1", "2", "3", "4", "5"]


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_devices):
    """Add sensors for passed config_entry in HA."""

    async_api = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = hass.data[DOMAIN]["coordinator"]

    async_add_devices([EdilkaminClimateEntity(async_api, coordinator)])


class EdilkaminClimateEntity(CoordinatorEntity, ClimateEntity):
    """Representation of a Climate."""

    def __init__(self, api: EdilkaminAsyncApi, coordinator) -> None:
        """Initialize the climate."""
        super().__init__(coordinator)
        self.api = api

        self._state = None
        self._attr_current_temperature = None
        self._attr_target_temperature = None

        self._attr_fan_modes = FAN_MODES_MANAGED
        self._attr_fan_mode = "1"  # default fan speed

        self._attr_hvac_mode = HVACMode.OFF  # default hvac mode
        self._mac_address = api.get_mac_address()
        self._attr_max_temp = 24
        self._attr_min_temp = 14

        self._attr_name = "Edilkamin climate"
        self._attr_device_info = {"identifiers": {("edilkamin", self._mac_address)}}

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self._mac_address}_climate"

    @property
    def temperature_unit(self):
        """The unit of temperature measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """List of available operation modes."""
        return CLIMATE_HVAC_MODE_MANAGED

    @property
    def supported_features(self):
        """Bitmap of supported features."""
        return ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        await self.api.set_fan_speed(fan_mode)
        await self.coordinator.async_refresh()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            target_tmp = kwargs.get(ATTR_TEMPERATURE)
            await self.api.set_temperature(target_tmp)
        await self.coordinator.async_refresh()

    def _handle_coordinator_update(self) -> None:
        self._attr_current_temperature = self.coordinator.get_temperature()
        self._attr_target_temperature = self.coordinator.get_target_temperature()
        self._attr_fan_mode = str(self.coordinator.get_fan_speed())

        power = self.coordinator.get_power_status()
        if power is True:
            self._attr_hvac_mode = HVACMode.HEAT
        else:
            self._attr_hvac_mode = HVACMode.OFF

        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode not in CLIMATE_HVAC_MODE_MANAGED:
            raise ValueError(f"Unsupported HVAC mode: {hvac_mode}")

        if hvac_mode == HVACMode.OFF:
            await self.api.disable_power()

        if hvac_mode == HVACMode.HEAT:
            await self.api.enable_power()

        await self.coordinator.async_refresh()

    async def async_turn_on(self):
        """Turn on."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self):
        """Turn off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
