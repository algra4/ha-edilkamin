"""Platform for fan integration."""

from __future__ import annotations

import logging
import math

from custom_components.edilkamin.api.edilkamin_async_api import (
    EdilkaminAsyncApi,
    HttpException,
)

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SPEED_RANGE = (1, 5)  # away is not included in speeds and instead mapped to off


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add sensors for passed config_entry in HA."""
    async_api = hass.data[DOMAIN][config_entry.entry_id]

    nb_fans = await async_api.get_nb_fans()

    fans = [EdilkaminFan(async_api, 1)]

    if nb_fans > 1:
        fans.extend(EdilkaminFan(async_api, i) for i in range(2, nb_fans + 1))

    async_add_devices(fans)


class EdilkaminFan(FanEntity):
    """Representation of a Fan."""

    def __init__(self, api: EdilkaminAsyncApi, index: int) -> None:
        """Initialize the fan."""
        self._api = api
        self._mac_address = api.get_mac_address()
        self._index = index
        self._current_speed = None
        self._current_state = False

        self._attr_name = f"Fan {index}"
        self._attr_device_info = {"identifiers": {("edilkamin", self._mac_address)}}

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self._mac_address}_fan{self._index}"

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self._current_state is False:
            return None

        if self._current_speed is None:
            return None
        return ranged_value_to_percentage(SPEED_RANGE, self._current_speed)

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
        self._current_speed = math.ceil(
            percentage_to_ranged_value(SPEED_RANGE, percentage)
        )

        await self._api.set_fan_speed(self._current_speed, self._index)
        self.schedule_update_ha_state()

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            self._current_state = await self._api.get_power_status()
            if self._current_state is True:
                self._current_speed = await self._api.get_fan_speed(self._index)
        except HttpException as err:
            _LOGGER.error(str(err))
            return

    async def async_turn_on(
        self,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Turn on the entity."""

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the entity."""
