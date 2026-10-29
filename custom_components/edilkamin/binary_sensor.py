"""Platform for sensor integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from custom_components.edilkamin.api.edilkamin_async_api import (
        EdilkaminAsyncApi,
    )

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add sensors for passed config_entry in HA."""
    coordinator = hass.data[DOMAIN]["coordinators"][config_entry.entry_id]
    async_api = hass.data[DOMAIN][config_entry.entry_id]

    if coordinator.pellet is not None and coordinator.pellet.enabled:
        async_add_devices([EdilkaminPelletIncompleteSensor(coordinator)])

    async_add_devices(
        [
            EdilkaminTankBinarySensor(coordinator),
            EdilkaminCheckBinarySensor(async_api),
        ]
    )


class EdilkaminPelletIncompleteSensor(CoordinatorEntity, BinarySensorEntity):
    """Sticky indication that some enabled consumption could not be estimated."""

    _attr_name = "Pellet estimate incomplete"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator)
        mac = coordinator.get_mac_address()
        self._attr_unique_id = f"{mac}_pellet_estimate_incomplete"
        self._attr_device_info = {"identifiers": {(DOMAIN, mac)}}

    @property
    def is_on(self):
        return self.coordinator.pellet.incomplete

    @property
    def extra_state_attributes(self):
        return {"reasons": list(self.coordinator.pellet.state["reasons"])}

    @property
    def available(self):
        return super().available and not self.coordinator.pellet.storage_invalid


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


class EdilkaminCheckBinarySensor(BinarySensorEntity):
    """Representation of a Sensor."""

    def __init__(self, api: EdilkaminAsyncApi) -> None:
        """Initialize the sensor."""
        self._state = None
        self._api = api
        self._mac_address = self._api.get_mac_address()

        self._attr_name = "Check configuration"
        self._attr_device_info = {"identifiers": {("edilkamin", self._mac_address)}}
        self._attr_icon = "mdi:check-circle"

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
        return f"{self._mac_address}_check_binary_sensor"

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            await self._api.check()
            self._state = False
            self.async_write_ha_state()
        except Exception:
            self._state = True
            self.async_write_ha_state()
            _LOGGER.exception("Exception occurred during check configuration")
