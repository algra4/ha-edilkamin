"""Platform for sensor integration."""
from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.const import UnitOfTemperature

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from custom_components.edilkamin.api.edilkamin_async_api import EdilkaminAsyncApi, HttpException

_LOGGER = logging.getLogger(__name__)


# https://github.com/home-assistant/example-custom-config/blob/master/custom_components/detailed_hello_world_push/sensor.py
async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add sensors for passed config_entry in HA."""

    async_api = hass.data[DOMAIN][config_entry.entry_id]

    async_add_devices(
        [
            EdilkaminTemperatureSensor(async_api),
            EdilkaminFan1Sensor(async_api),
            EdilkaminAlarmSensor(async_api),
            EdilkaminActualPowerSensor(async_api),
        ]
    )


class EdilkaminTemperatureSensor(SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, api: EdilkaminAsyncApi):
        """Initialize the sensor."""
        self._state = None
        self.api = api
        self.mac_address = api.get_mac_address()

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

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            self._state = await self.api.get_temperature()
        except HttpException as err:
            _LOGGER.error(str(err))
            return


class EdilkaminFan1Sensor(SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, api: EdilkaminAsyncApi):
        """Initialize the sensor."""
        self._state = None
        self.api = api
        self.mac_address = api.get_mac_address()
        self._attr_icon = "mdi:fan"

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SensorDeviceClass.POWER

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self.mac_address}_fan1_sensor"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            self._state = await self.api.get_fan_1_speed()
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
