"""Tests for the buffer tank and boiler water temperature sensors."""

import asyncio
from unittest.mock import Mock

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature
import pytest

from custom_components.edilkamin.sensor import (
    EdilkaminWaterTemperatureSensor,
    async_setup_entry,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator instance."""
    coordinator = Mock()
    coordinator.get_mac_address = Mock(return_value="00:11:22:33:44:55")
    coordinator.get_nb_fans = Mock(return_value=1)
    coordinator.async_add_listener = Mock()
    coordinator.last_update_success = True
    return coordinator


class TestEdilkaminWaterTemperatureSensor:
    """Test EdilkaminWaterTemperatureSensor class."""

    def test_init(self, mock_coordinator):
        """Test sensor initialization and metadata."""
        sensor = EdilkaminWaterTemperatureSensor(
            mock_coordinator, "puffer", "Buffer temperature"
        )

        assert sensor._temperature_key == "puffer"
        assert sensor._attr_name == "Buffer temperature"
        assert sensor._attr_icon == "mdi:thermometer-water"
        assert sensor.unique_id == "00:11:22:33:44:55_puffer_temperature"
        assert sensor.device_class == SensorDeviceClass.TEMPERATURE
        assert sensor.native_unit_of_measurement == UnitOfTemperature.CELSIUS
        assert sensor.state_class == SensorStateClass.MEASUREMENT

    def test_buffer_and_boiler_have_distinct_unique_ids(self, mock_coordinator):
        """Test the two water sensors expose distinct unique ids."""
        buffer = EdilkaminWaterTemperatureSensor(
            mock_coordinator, "puffer", "Buffer temperature"
        )
        boiler = EdilkaminWaterTemperatureSensor(
            mock_coordinator, "boiler", "Boiler temperature"
        )

        assert buffer.unique_id != boiler.unique_id

    def test_native_value_with_valid_reading(self, mock_coordinator):
        """Test native_value returns the coordinator water temperature."""
        mock_coordinator.get_water_temperature = Mock(return_value=56.8)
        sensor = EdilkaminWaterTemperatureSensor(
            mock_coordinator, "puffer", "Buffer temperature"
        )

        assert sensor.native_value == 56.8
        assert sensor.available
        mock_coordinator.get_water_temperature.assert_called_with("puffer")

    def test_native_value_zero_is_valid(self, mock_coordinator):
        """Test a zero reading is treated as valid (unlike the ambient sensor)."""
        mock_coordinator.get_water_temperature = Mock(return_value=0)
        sensor = EdilkaminWaterTemperatureSensor(
            mock_coordinator, "puffer", "Buffer temperature"
        )

        assert sensor.native_value == 0
        assert sensor.available

    @pytest.mark.parametrize("value", [None, True, False, "invalid"])
    def test_native_value_rejects_invalid_readings(self, mock_coordinator, value):
        """Test None, booleans and non-numeric readings are unavailable."""
        mock_coordinator.get_water_temperature = Mock(return_value=value)
        sensor = EdilkaminWaterTemperatureSensor(
            mock_coordinator, "puffer", "Buffer temperature"
        )

        assert sensor.native_value is None
        assert not sensor.available

    def test_unavailable_when_cloud_update_failed(self, mock_coordinator):
        """Test the sensor is unavailable when the last cloud update failed."""
        mock_coordinator.get_water_temperature = Mock(return_value=56.8)
        mock_coordinator.last_update_success = False
        sensor = EdilkaminWaterTemperatureSensor(
            mock_coordinator, "puffer", "Buffer temperature"
        )

        assert not sensor.available


class TestWaterTemperatureSetup:
    """Test async_setup_entry only creates the reported water sensors."""

    @pytest.mark.parametrize(
        ("temperatures", "expected_keys"),
        [
            ({"puffer": 56.8, "boiler": 56.3}, {"puffer", "boiler"}),
            ({"puffer": 0}, {"puffer"}),
            ({"enviroment": 22.8}, set()),
        ],
    )
    def test_setup_only_creates_reported_sensors(
        self, mock_coordinator, temperatures, expected_keys
    ):
        """Test sensors are created only for the hydronic keys the stove reports."""
        mock_coordinator.get_temperatures = Mock(return_value=temperatures)
        hass = Mock()
        mock_coordinator.pellet = None
        hass.data = {"edilkamin": {"coordinators": {"test": mock_coordinator}}}
        add_entities = Mock()

        asyncio.run(async_setup_entry(hass, Mock(entry_id="test"), add_entities))

        sensors = add_entities.call_args.args[0]
        keys = {
            sensor._temperature_key
            for sensor in sensors
            if isinstance(sensor, EdilkaminWaterTemperatureSensor)
        }
        assert keys == expected_keys
