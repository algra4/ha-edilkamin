"""Platform for sensor integration."""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

OPERATIONAL_STATES = {
    0: "Off",
    1: "Ignition",
    2: "On",
    3: "Shutdown",
    4: "Cooling",
    5: "Alarm",
    6: "Final cleaning",
    7: "Unknown",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
):
    """Add sensors for passed config_entry in HA."""

    coordinator = hass.data[DOMAIN]["coordinator"]

    sensors = [
        EdilkaminTemperatureSensor(coordinator),
        EdilkaminFanSensor(coordinator, 1),
        EdilkaminAlarmSensor(coordinator),
        EdilkaminActualPowerSensor(coordinator),
        EdilkaminOperationalSensor(coordinator),
    ]

    nb_fans = coordinator.get_nb_fans()

    if nb_fans > 1:
        sensors.extend(
            EdilkaminFanSensor(coordinator, i) for i in range(2, nb_fans + 1)
        )

    async_add_devices(sensors)


class EdilkaminTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._state = None
        self._mac_address = self.coordinator.get_mac_address()

        self._attr_name = "Temperature"
        self._attr_device_info = {"identifiers": {("edilkamin", self._mac_address)}}
        self._attr_icon = "mdi:thermometer"

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
        return f"{self._mac_address}_temperature"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.coordinator.get_temperature()
        self.async_write_ha_state()


class EdilkaminFanSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator, index: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._state = None
        self._mac_address = self.coordinator.get_mac_address()
        self._attr_icon = "mdi:fan"
        self._index = index

        self._attr_name = f"Fan {index}"
        self._attr_device_info = {"identifiers": {("edilkamin", self._mac_address)}}

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SensorDeviceClass.POWER

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self._mac_address}_fan{self._index}_sensor"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def _handle_coordinator_update(self) -> None:
        """Fetch new state data for the sensor."""
        self._state = self.coordinator.get_fan_speed(self._index)
        self.async_write_ha_state()


class EdilkaminAlarmSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._state = None
        self._mac_address = self.coordinator.get_mac_address()
        self._attr_icon = "mdi:alert"
        self._attributes: dict[str, Any] = {}

        self._attr_name = "Nb alarms"
        self._attr_device_info = {"identifiers": {("edilkamin", self._mac_address)}}

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SensorDeviceClass.POWER

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self._mac_address}_nb_alarms_sensor"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return attributes for the sensor."""
        return self._attributes

    def _handle_coordinator_update(self) -> None:
        """Fetch new state data for the sensor."""
        self._state = self.coordinator.get_nb_alarms()
        alarms = self.coordinator.get_alarms()

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
        self.async_write_ha_state()


class EdilkaminActualPowerSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._state = None
        self._mac_address = self.coordinator.get_mac_address()

        self._attr_name = "Actual power"
        self._attr_device_info = {"identifiers": {("edilkamin", self._mac_address)}}
        self._attr_icon = "mdi:flash"

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
        return f"{self._mac_address}_actual_power"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def _handle_coordinator_update(self) -> None:
        """Fetch new state data for the sensor."""
        self._state = self.coordinator.get_actual_power()
        self.async_write_ha_state()


class EdilkaminOperationalSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._state = None
        self._mac_address = self.coordinator.get_mac_address()
        self._attr_icon = "mdi:eye"
        self._attributes: dict[str, Any] = {}

        self._attr_name = "Operational phase"
        self._attr_options = list(OPERATIONAL_STATES.values())
        self._attr_device_info = {"identifiers": {("edilkamin", self._mac_address)}}

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SensorDeviceClass.ENUM

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self._mac_address}_operational_phase_sensor"

    def _handle_coordinator_update(self) -> None:
        """Fetch new state data for the sensor."""
        op_state = self.coordinator.get_operational_phase()

        if op_state in OPERATIONAL_STATES:
            self._attr_native_value = OPERATIONAL_STATES[op_state]
        else:
            # Error operational code unknown, shows only the code
            self._attr_native_value = OPERATIONAL_STATES[7]

        additional_att = {"value": op_state}
        self._attr_extra_state_attributes = additional_att
        self.async_write_ha_state()
