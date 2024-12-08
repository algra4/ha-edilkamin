"""Platform for fan integration."""
from __future__ import annotations

import logging
import math

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.fan import (
    FanEntityFeature,
    FanEntity
)
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DOMAIN
from custom_components.edilkamin.api.edilkamin_async_api import EdilkaminAsyncApi, HttpException

_LOGGER = logging.getLogger(__name__)

SPEED_RANGE = (1, 5)  # away is not included in speeds and instead mapped to off


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add sensors for passed config_entry in HA."""
    async_api = hass.data[DOMAIN][config_entry.entry_id]

    async_add_devices([EdilkaminFan(async_api)])


class EdilkaminFan(FanEntity):
    """Representation of a Fan."""

    def __init__(self, api: EdilkaminAsyncApi):
        """Initialize the fan."""
        self.api = api
        self.mac_address = api.get_mac_address()

        self.current_speed = None
        self.current_state = False

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self.mac_address}_fan1"


    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self.current_state is False:
            return None

        if self.current_speed is None:
            return None
        return ranged_value_to_percentage(SPEED_RANGE, self.current_speed)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(SPEED_RANGE)

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return FanEntityFeature.SET_SPEED

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        self.current_speed = math.ceil(
            percentage_to_ranged_value(SPEED_RANGE, percentage)
        )

        await self.api.set_fan_1_speed(self.current_speed)
        self.schedule_update_ha_state()

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            self.current_state = await self.api.get_power_status()
            if self.current_state is True:
                self.current_speed = await self.api.get_fan_1_speed()
        except HttpException as err:
            _LOGGER.error(str(err))
            return

    async def async_turn_on(
            self,
            speed: str = None,
            percentage: int = None,
            preset_mode: str = None,
            **kwargs,
    ) -> None:
        """Turn on the entity."""

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the entity."""
