"""Hydronic temperature sensors use the coordinator's existing cloud data."""

import asyncio
import unittest
from unittest.mock import Mock

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature

from custom_components.edilkamin.sensor import (
    EdilkaminWaterTemperatureSensor,
    async_setup_entry,
)


class TestHydronicTemperature(unittest.TestCase):
    """Cover water readings and devices that do not report hydronic data."""

    def setUp(self):
        self.coordinator = Mock()
        self.coordinator.get_mac_address.return_value = "00:11:22:33:44:55"
        self.coordinator.get_nb_fans.return_value = 1
        self.coordinator.last_update_success = True
        self.coordinator.data = {
            "status": {"temperatures": {"puffer": 56.8, "boiler": 56.3}},
        }

    def sensor(self, key="puffer"):
        return EdilkaminWaterTemperatureSensor(self.coordinator, key, key)

    def test_both_readings_and_distinct_ids(self):
        buffer = self.sensor()
        boiler = self.sensor("boiler")
        assert buffer.native_value == 56.8
        assert boiler.native_value == 56.3
        assert buffer.unique_id != boiler.unique_id
        assert buffer.device_class == SensorDeviceClass.TEMPERATURE
        assert buffer.native_unit_of_measurement == UnitOfTemperature.CELSIUS
        assert buffer.state_class == SensorStateClass.MEASUREMENT

    def test_updated_reading(self):
        sensor = self.sensor()
        self.coordinator.data["status"]["temperatures"]["puffer"] = 60.2
        assert sensor.native_value == 60.2

    def test_zero_is_valid(self):
        self.coordinator.data["status"]["temperatures"]["puffer"] = 0
        assert self.sensor().native_value == 0
        assert self.sensor().available

    def test_missing_or_invalid_reading_is_unavailable(self):
        for value in (None, True, "invalid"):
            with self.subTest(value=value):
                self.coordinator.data["status"]["temperatures"]["puffer"] = value
                assert self.sensor().native_value is None
                assert not self.sensor().available
        for data in (None, {}, {"status": {}}, {"status": {"temperatures": {}}}):
            with self.subTest(data=data):
                self.coordinator.data = data
                assert self.sensor().native_value is None
                assert not self.sensor().available

    def test_cloud_failure_marks_reading_unavailable(self):
        self.coordinator.last_update_success = False
        assert not self.sensor().available

    def test_setup_only_creates_reported_sensors(self):
        for temperatures, expected in (
            ({"puffer": 56.8, "boiler": 56.3}, {"puffer", "boiler"}),
            ({"puffer": 0}, {"puffer"}),
            ({"enviroment": 22.8}, set()),
        ):
            with self.subTest(temperatures=temperatures):
                self.coordinator.data = {"status": {"temperatures": temperatures}}
                hass = Mock()
                hass.data = {"edilkamin": {"coordinator": self.coordinator}}
                add_entities = Mock()
                asyncio.run(async_setup_entry(hass, Mock(), add_entities))
                sensors = add_entities.call_args.args[0]
                keys = {
                    sensor._temperature_key
                    for sensor in sensors
                    if isinstance(sensor, EdilkaminWaterTemperatureSensor)
                }
                assert keys == expected


if __name__ == "__main__":
    unittest.main()
