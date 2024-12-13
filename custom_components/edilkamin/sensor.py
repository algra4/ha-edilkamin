"""Platform for sensor integration."""

from __future__ import annotations

import logging
import time
from typing import Any

from custom_components.edilkamin.api.edilkamin_async_api import (
    EdilkaminAsyncApi,
    HttpException,
)

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import DOMAIN
from .coordinator import EdilkaminCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
):
    """Add sensors for passed config_entry in HA."""

    async_api = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = hass.data[DOMAIN]["coordinator"]

    sensors = [
        EdilkaminTemperatureSensor(coordinator),
        EdilkaminFanSensor(async_api, 1),
        EdilkaminAlarmSensor(async_api),
        EdilkaminActualPowerSensor(async_api),
    ]

    nb_fans = await async_api.get_nb_fans()

    if nb_fans > 1:
        sensors.extend(EdilkaminFanSensor(async_api, i) for i in range(2, nb_fans + 1))

    async_add_devices(sensors)


class EdilkaminTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._state = None
        self.mac_address = self.coordinator.get_mac_address()

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SensorDeviceClass.TEMPERATURE

    @property
    def native_unit_of_measurement(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return UnitOfTemperature.CELSIUS

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self.mac_address}_temperature"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.coordinator.get_temperature()
        self.async_write_ha_state()


class EdilkaminFanSensor(SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, api: EdilkaminAsyncApi, index: int):
        """Initialize the sensor."""
        self._state = None
        self.api = api
        self.mac_address = api.get_mac_address()
        self._attr_icon = "mdi:fan"
        self._index = index

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SensorDeviceClass.POWER

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self.mac_address}_fan{self._index}_sensor"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            self._state = await self.api.get_fan_speed(self._index)
        except HttpException as err:
            _LOGGER.error(str(err))
            return


class EdilkaminAlarmSensor(SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, api: EdilkaminAsyncApi):
        """Initialize the sensor."""
        self._state = None
        self.api = api
        self.mac_address = api.get_mac_address()
        self._attr_icon = "mdi:alert"
        self._attributes: dict[str, Any] = {}

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SensorDeviceClass.POWER

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self.mac_address}_nb_alarms_sensor"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return attributes for the sensor."""
        return self._attributes

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            self._state = await self.api.get_nb_alarms()
            alarms = await self.api.get_alarms()

            errors = {
                "errors": [],
            }

            for alarm in alarms:
                data = {
                    "type": alarm["type"],
                    "timestamp": time.strftime(
                        "%d-%m-%Y %H:%M:%S", time.localtime(alarm["timestamp"])
                    ),
                }
                errors["errors"].append(data)

            self._attributes = errors

        except HttpException as err:
            _LOGGER.error(str(err))
            return


class EdilkaminActualPowerSensor(SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, api: EdilkaminAsyncApi):
        """Initialize the sensor."""
        self._state = None
        self.api = api
        self.mac_address = api.get_mac_address()

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SensorDeviceClass.POWER

    @property
    def native_unit_of_measurement(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return None

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self.mac_address}_actual_power"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            self._state = await self.api.get_actual_power()
        except HttpException as err:
            _LOGGER.error(str(err))
            return
