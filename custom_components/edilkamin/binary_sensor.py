"""Platform for sensor integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, _config_entry, async_add_devices):
    """Add sensors for passed config_entry in HA."""
    coordinator = hass.data[DOMAIN]["coordinator"]

    async_add_devices(
        [
            EdilkaminTankBinarySensor(coordinator),
            EdilkaminCheckBinarySensor(coordinator),
        ]
    )


class EdilkaminTankBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._state = None
        self._mac_address = self.coordinator.get_mac_address()
        self._attr_icon = "mdi:storage-tank"

        self._attr_name = "Tank"
        self._attr_device_info = {"identifiers": {("edilkamin", self._mac_address)}}

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return BinarySensorDeviceClass.PROBLEM

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self._mac_address}_tank_binary_sensor"

    def _handle_coordinator_update(self) -> None:
        """Fetch new state data for the sensor."""
        self._state = self.coordinator.get_status_tank()
        self.async_write_ha_state()


class EdilkaminCheckBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Report coordinator update failures without sending a device command."""

    # Retain the legacy name and unique ID for existing dashboards/history.
    _attr_name = "Check configuration"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:check-circle"

    def __init__(self, coordinator) -> None:
        """Initialize the passive health diagnostic."""
        super().__init__(coordinator)
        mac = coordinator.get_mac_address()
        self._attr_unique_id = f"{mac}_check_binary_sensor"
        self._attr_device_info = {"identifiers": {(DOMAIN, mac)}}

    @property
    def available(self) -> bool:
        """Stay available on coordinator failure so the problem remains visible."""
        return True

    @property
    def is_on(self) -> bool:
        """Report whether the latest coordinator update failed."""
        return not self.coordinator.last_update_success

    async def async_update(self) -> None:
        """Keep manual entity updates passive too; the coordinator owns polling."""
