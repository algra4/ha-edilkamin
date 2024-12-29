"""Platform for climate integration.

Inspired by nghaye/ha-edilkamin.
"""

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


PRESET_AUTO = "Auto"
PRESET_1 = "Manual P1"
PRESET_2 = "Manual P2"
PRESET_3 = "Manual P3"
PRESET_4 = "Manual P4"
PRESET_5 = "Manual P5"

PRESET_MODES = [PRESET_AUTO, PRESET_1, PRESET_2, PRESET_3, PRESET_4, PRESET_5]
PRESET_MODE_TO_POWER = {
    "Manual P1": 1,
    "Manual P2": 2,
    "Manual P3": 3,
    "Manual P4": 4,
    "Manual P5": 5,
}


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

        self._attr_hvac_modes = CLIMATE_HVAC_MODE_MANAGED
        self._attr_hvac_mode = HVACMode.OFF  # default hvac mode

        self._mac_address = api.get_mac_address()
        self._attr_max_temp = 24
        self._attr_min_temp = 14

        self._attr_preset_modes = PRESET_MODES
        self._attr_preset_mode = PRESET_AUTO

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
    def supported_features(self):
        """Bitmap of supported features."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

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

        if self.coordinator.is_auto():
            self._attr_preset_mode = PRESET_AUTO
        else:
            manual_power = self.coordinator.get_manual_power()
            self._attr_preset_mode = PRESET_MODES[manual_power]

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

    async def async_set_preset_mode(self, preset_mode) -> None:
        """Set new target preset mode."""
        if preset_mode == PRESET_AUTO:
            await self.api.enable_auto_mode()
        else:
            await self.api.disable_auto_mode()
            await self.api.set_manual_power_level(PRESET_MODE_TO_POWER[preset_mode])
        await self.coordinator.async_refresh()
