"""Tests for sensor entities."""

from unittest.mock import Mock

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature
import pytest

from custom_components.edilkamin.sensor import (
    OPERATIONAL_STATES,
    EdilkaminActualPowerSensor,
    EdilkaminAlarmSensor,
    EdilkaminAutonomySensor,
    EdilkaminFanSensor,
    EdilkaminOperationalSensor,
    EdilkaminPowerOnsSensor,
    EdilkaminTemperatureSensor,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator instance."""
    coordinator = Mock()
    coordinator.get_mac_address = Mock(return_value="00:11:22:33:44:55")
    coordinator.async_add_listener = Mock()
    return coordinator


class TestEdilkaminTemperatureSensor:
    """Test EdilkaminTemperatureSensor class."""

    def test_init(self, mock_coordinator):
        """Test sensor initialization."""
        sensor = EdilkaminTemperatureSensor(mock_coordinator)

        assert sensor._state is None
        assert sensor._mac_address == "00:11:22:33:44:55"
        assert sensor._attr_name == "Temperature"
        assert sensor._attr_icon == "mdi:thermometer"
        assert sensor.unique_id == "00:11:22:33:44:55_temperature"

    def test_device_class(self, mock_coordinator):
        """Test device class property."""
        sensor = EdilkaminTemperatureSensor(mock_coordinator)

        assert sensor.device_class == SensorDeviceClass.TEMPERATURE

    def test_native_unit_of_measurement(self, mock_coordinator):
        """Test unit of measurement."""
        sensor = EdilkaminTemperatureSensor(mock_coordinator)

        assert sensor.native_unit_of_measurement == UnitOfTemperature.CELSIUS

    def test_handle_coordinator_update_with_valid_temperature(self, mock_coordinator):
        """Test update with valid temperature value."""
        sensor = EdilkaminTemperatureSensor(mock_coordinator)
        sensor.async_write_ha_state = Mock()
        mock_coordinator.get_temperature = Mock(return_value=22.5)

        sensor._handle_coordinator_update()

        assert sensor._state == 22.5
        sensor.async_write_ha_state.assert_called_once()

    def test_handle_coordinator_update_with_zero_temperature(self, mock_coordinator):
        """Test update with zero temperature - should not update state."""
        sensor = EdilkaminTemperatureSensor(mock_coordinator)
        sensor.async_write_ha_state = Mock()
        sensor._state = 20.0  # Previous valid state
        mock_coordinator.get_temperature = Mock(return_value=0)

        sensor._handle_coordinator_update()

        assert sensor._state == 20.0
        sensor.async_write_ha_state.assert_called_once()

    def test_handle_coordinator_update_with_none_temperature(self, mock_coordinator):
        """Test update with None temperature - should not update state."""
        sensor = EdilkaminTemperatureSensor(mock_coordinator)
        sensor.async_write_ha_state = Mock()
        sensor._state = 18.5  # Previous valid state
        mock_coordinator.get_temperature = Mock(return_value=None)

        sensor._handle_coordinator_update()

        # State should remain unchanged
        assert sensor._state == 18.5
        sensor.async_write_ha_state.assert_called_once()

    def test_handle_coordinator_update_zero_then_valid(self, mock_coordinator):
        """Test that valid temperature updates after zero."""
        sensor = EdilkaminTemperatureSensor(mock_coordinator)
        sensor.async_write_ha_state = Mock()

        # First update with zero
        mock_coordinator.get_temperature = Mock(return_value=0)
        sensor._handle_coordinator_update()
        assert sensor._state is None

        # Second update with valid temperature
        mock_coordinator.get_temperature = Mock(return_value=23.0)
        sensor._handle_coordinator_update()
        assert sensor._state == 23.0


class TestEdilkaminFanSensor:
    """Test EdilkaminFanSensor class."""

    def test_init_fan1(self, mock_coordinator):
        """Test fan sensor initialization for fan 1."""
        sensor = EdilkaminFanSensor(mock_coordinator, 1)

        assert sensor._state is None
        assert sensor._mac_address == "00:11:22:33:44:55"
        assert sensor._attr_name == "Fan 1"
        assert sensor._attr_icon == "mdi:fan"
        assert sensor._index == 1
        assert sensor.unique_id == "00:11:22:33:44:55_fan1_sensor"

    def test_init_fan2(self, mock_coordinator):
        """Test fan sensor initialization for fan 2."""
        sensor = EdilkaminFanSensor(mock_coordinator, 2)

        assert sensor._attr_name == "Fan 2"
        assert sensor._index == 2
        assert sensor.unique_id == "00:11:22:33:44:55_fan2_sensor"

    def test_device_class(self, mock_coordinator):
        """Test device class property."""
        sensor = EdilkaminFanSensor(mock_coordinator, 1)

        assert sensor.device_class == SensorDeviceClass.POWER

    def test_handle_coordinator_update(self, mock_coordinator):
        """Test update with fan speed data."""
        sensor = EdilkaminFanSensor(mock_coordinator, 1)
        sensor.async_write_ha_state = Mock()
        mock_coordinator.get_fan_speed = Mock(return_value=3)

        sensor._handle_coordinator_update()

        mock_coordinator.get_fan_speed.assert_called_once_with(1)
        assert sensor._state == 3
        sensor.async_write_ha_state.assert_called_once()


class TestEdilkaminAlarmSensor:
    """Test EdilkaminAlarmSensor class."""

    def test_init(self, mock_coordinator):
        """Test alarm sensor initialization."""
        sensor = EdilkaminAlarmSensor(mock_coordinator)

        assert sensor._state is None
        assert sensor._mac_address == "00:11:22:33:44:55"
        assert sensor._attr_name == "Nb alarms"
        assert sensor._attr_icon == "mdi:alert"
        assert sensor._attributes == {}
        assert sensor.unique_id == "00:11:22:33:44:55_nb_alarms_sensor"

    def test_handle_coordinator_update_with_alarms(self, mock_coordinator):
        """Test update with alarm data."""
        sensor = EdilkaminAlarmSensor(mock_coordinator)
        sensor.async_write_ha_state = Mock()

        mock_coordinator.get_nb_alarms = Mock(return_value=2)
        mock_coordinator.get_alarms = Mock(
            return_value=[
                {"type": 1, "timestamp": 1234567890},
                {"type": 2, "timestamp": 1234567900},
            ]
        )

        sensor._handle_coordinator_update()

        assert sensor._state == 2
        assert "errors" in sensor._attributes
        assert len(sensor._attributes["errors"]) == 2
        assert sensor._attributes["errors"][0]["type"] == 1
        assert sensor._attributes["errors"][1]["type"] == 2
        sensor.async_write_ha_state.assert_called_once()

    def test_handle_coordinator_update_no_alarms(self, mock_coordinator):
        """Test update with no alarms."""
        sensor = EdilkaminAlarmSensor(mock_coordinator)
        sensor.async_write_ha_state = Mock()

        mock_coordinator.get_nb_alarms = Mock(return_value=0)
        mock_coordinator.get_alarms = Mock(return_value=[])

        sensor._handle_coordinator_update()

        assert sensor._state == 0
        assert sensor._attributes == {"errors": []}
        sensor.async_write_ha_state.assert_called_once()


class TestEdilkaminActualPowerSensor:
    """Test EdilkaminActualPowerSensor class."""

    def test_init(self, mock_coordinator):
        """Test actual power sensor initialization."""
        sensor = EdilkaminActualPowerSensor(mock_coordinator)

        assert sensor._state is None
        assert sensor._mac_address == "00:11:22:33:44:55"
        assert sensor._attr_name == "Actual power"
        assert sensor._attr_icon == "mdi:flash"
        assert sensor.unique_id == "00:11:22:33:44:55_actual_power"

    def test_device_class(self, mock_coordinator):
        """Test device class property."""
        sensor = EdilkaminActualPowerSensor(mock_coordinator)

        assert sensor.device_class == SensorDeviceClass.POWER

    def test_native_unit_of_measurement(self, mock_coordinator):
        """Test unit of measurement is None."""
        sensor = EdilkaminActualPowerSensor(mock_coordinator)
        assert sensor.native_unit_of_measurement is None

    def test_handle_coordinator_update(self, mock_coordinator):
        """Test update with actual power data."""
        sensor = EdilkaminActualPowerSensor(mock_coordinator)
        sensor.async_write_ha_state = Mock()
        mock_coordinator.get_actual_power = Mock(return_value=5)

        sensor._handle_coordinator_update()

        assert sensor._state == 5
        sensor.async_write_ha_state.assert_called_once()


class TestEdilkaminOperationalSensor:
    """Test EdilkaminOperationalSensor class."""

    def test_init(self, mock_coordinator):
        """Test operational sensor initialization."""
        sensor = EdilkaminOperationalSensor(mock_coordinator)

        assert sensor._state is None
        assert sensor._mac_address == "00:11:22:33:44:55"
        assert sensor._attr_name == "Operational phase"
        assert sensor._attr_icon == "mdi:eye"
        assert sensor._attr_options == list(OPERATIONAL_STATES.values())
        assert sensor.unique_id == "00:11:22:33:44:55_operational_phase_sensor"

    def test_device_class(self, mock_coordinator):
        """Test device class property."""
        sensor = EdilkaminOperationalSensor(mock_coordinator)

        assert sensor.device_class == SensorDeviceClass.ENUM

    def test_handle_coordinator_update_valid_state(self, mock_coordinator):
        """Test update with valid operational state."""
        sensor = EdilkaminOperationalSensor(mock_coordinator)
        sensor.async_write_ha_state = Mock()
        mock_coordinator.get_operational_phase = Mock(return_value=2)

        sensor._handle_coordinator_update()

        assert sensor._attr_native_value == "On"
        assert sensor._attr_extra_state_attributes == {"value": 2}
        sensor.async_write_ha_state.assert_called_once()

    def test_handle_coordinator_update_unknown_state(self, mock_coordinator):
        """Test update with unknown operational state."""
        sensor = EdilkaminOperationalSensor(mock_coordinator)
        sensor.async_write_ha_state = Mock()
        mock_coordinator.get_operational_phase = Mock(return_value=99)

        sensor._handle_coordinator_update()

        assert sensor._attr_native_value == "Unknown"
        assert sensor._attr_extra_state_attributes == {"value": 99}
        sensor.async_write_ha_state.assert_called_once()

    def test_all_operational_states(self, mock_coordinator):
        """Test all defined operational states."""
        sensor = EdilkaminOperationalSensor(mock_coordinator)
        sensor.async_write_ha_state = Mock()

        for state_code, state_name in OPERATIONAL_STATES.items():
            if state_code != 7:  # Skip "Unknown" as it's the default
                mock_coordinator.get_operational_phase = Mock(return_value=state_code)
                sensor._handle_coordinator_update()
                assert sensor._attr_native_value == state_name


class TestEdilkaminAutonomySensor:
    """Test EdilkaminAutonomySensor class."""

    def test_init(self, mock_coordinator):
        """Test autonomy sensor initialization."""
        sensor = EdilkaminAutonomySensor(mock_coordinator)

        assert sensor._state is None
        assert sensor._mac_address == "00:11:22:33:44:55"
        assert sensor._attr_name == "Autonomy"
        assert sensor._attr_icon == "mdi:timer"
        assert sensor.unique_id == "00:11:22:33:44:55_autonomy"
        assert "description" in sensor._attr_extra_state_attributes

    def test_device_class(self, mock_coordinator):
        """Test device class property."""
        sensor = EdilkaminAutonomySensor(mock_coordinator)

        assert sensor.device_class == SensorDeviceClass.DURATION

    def test_native_unit_of_measurement(self, mock_coordinator):
        """Test unit of measurement."""
        sensor = EdilkaminAutonomySensor(mock_coordinator)
        assert sensor.native_unit_of_measurement == "min"

    def test_handle_coordinator_update_with_data(self, mock_coordinator):
        """Test update with autonomy data."""
        sensor = EdilkaminAutonomySensor(mock_coordinator)
        sensor.async_write_ha_state = Mock()
        mock_coordinator.get_autonomy_second = Mock(return_value=3600)

        sensor._handle_coordinator_update()

        # 3600 seconds = 60 minutes, divmod returns (60, 0)
        assert sensor._state == "(60, 0)"
        sensor.async_write_ha_state.assert_called_once()

    def test_handle_coordinator_update_with_none(self, mock_coordinator):
        """Test update with None autonomy - should return early."""
        sensor = EdilkaminAutonomySensor(mock_coordinator)
        sensor.async_write_ha_state = Mock()
        sensor._state = "previous_value"
        mock_coordinator.get_autonomy_second = Mock(return_value=None)

        sensor._handle_coordinator_update()

        # State should not be updated, async_write_ha_state should not be called
        assert sensor._state == "previous_value"
        sensor.async_write_ha_state.assert_not_called()


class TestEdilkaminPowerOnsSensor:
    """Test EdilkaminPowerOnsSensor class."""

    def test_init(self, mock_coordinator):
        """Test power ons sensor initialization."""
        sensor = EdilkaminPowerOnsSensor(mock_coordinator)

        assert sensor._state is None
        assert sensor._mac_address == "00:11:22:33:44:55"
        assert sensor._attr_name == "Power ons"
        assert sensor._attr_icon == "mdi:counter"
        assert sensor.unique_id == "00:11:22:33:44:55_power_ons"

    def test_state_class(self, mock_coordinator):
        """Test state class property."""
        sensor = EdilkaminPowerOnsSensor(mock_coordinator)

        assert sensor._attr_state_class == SensorStateClass.MEASUREMENT

    def test_handle_coordinator_update(self, mock_coordinator):
        """Test update with power ons data."""
        sensor = EdilkaminPowerOnsSensor(mock_coordinator)
        sensor.async_write_ha_state = Mock()
        mock_coordinator.get_power_ons = Mock(return_value=42)

        sensor._handle_coordinator_update()

        assert sensor._state == 42
        sensor.async_write_ha_state.assert_called_once()
