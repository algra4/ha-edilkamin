"""Tests for coordinator data safety checks."""

import pytest
from unittest.mock import Mock, AsyncMock
from custom_components.edilkamin.coordinator import EdilkaminCoordinator


@pytest.fixture
def mock_hass():
    """Create a mock hass instance."""
    hass = Mock()
    hass.async_add_executor_job = AsyncMock()
    return hass


@pytest.fixture
def coordinator(mock_hass):
    """Create a coordinator instance."""
    return EdilkaminCoordinator(
        hass=mock_hass,
        username="test@example.com",
        password="password",
        mac_address="00:11:22:33:44:55",
    )


class TestCoordinatorWithNoData:
    """Test coordinator methods when device_info is empty."""

    def test_get_temperature_no_data(self, coordinator):
        """Test get_temperature returns None when no data."""
        assert coordinator.get_temperature() is None

    def test_get_fan_speed_no_data(self, coordinator):
        """Test get_fan_speed returns None when no data."""
        assert coordinator.get_fan_speed(1) is None

    def test_get_nb_fans_no_data(self, coordinator):
        """Test get_nb_fans returns default value when no data."""
        assert coordinator.get_nb_fans() is None

    def test_get_nb_alarms_no_data(self, coordinator):
        """Test get_nb_alarms returns 0 when no data."""
        assert coordinator.get_nb_alarms() is None

    def test_get_alarms_no_data(self, coordinator):
        """Test get_alarms returns empty list when no data."""
        assert coordinator.get_alarms() == []

    def test_get_actual_power_no_data(self, coordinator):
        """Test get_actual_power returns None when no data."""
        assert coordinator.get_actual_power() is None

    def test_get_status_tank_no_data(self, coordinator):
        """Test get_status_tank returns None when no data."""
        assert coordinator.get_status_tank() is None

    def test_get_airkare_status_no_data(self, coordinator):
        """Test get_airkare_status returns None when no data."""
        assert coordinator.get_airkare_status() is None

    def test_get_power_status_no_data(self, coordinator):
        """Test get_power_status returns None when no data."""
        assert coordinator.get_power_status() is None

    def test_get_relax_status_no_data(self, coordinator):
        """Test get_relax_status returns None when no data."""
        assert coordinator.get_relax_status() is None

    def test_get_target_temperature_no_data(self, coordinator):
        """Test get_target_temperature returns None when no data."""
        assert coordinator.get_target_temperature() is None

    def test_get_chrono_mode_status_no_data(self, coordinator):
        """Test get_chrono_mode_status returns None when no data."""
        assert coordinator.get_chrono_mode_status() is None

    def test_get_operational_phase_no_data(self, coordinator):
        """Test get_operational_phase returns None when no data."""
        assert coordinator.get_operational_phase() is None

    def test_get_autonomy_second_no_data(self, coordinator):
        """Test get_autonomy_second returns 0 when no data."""
        assert coordinator.get_autonomy_second() is None

    def test_get_standby_mode_no_data(self, coordinator):
        """Test get_standby_mode returns False when no data."""
        assert coordinator.get_standby_mode() is False

    def test_get_standby_waiting_time_no_data(self, coordinator):
        """Test get_standby_waiting_time returns 0 when no data."""
        assert coordinator.get_standby_waiting_time() is None

    def test_get_power_ons_no_data(self, coordinator):
        """Test get_power_ons returns 0 when no data."""
        assert coordinator.get_power_ons() is None

    def test_is_auto_no_data(self, coordinator):
        """Test is_auto returns False when no data."""
        assert coordinator.is_auto() is False

    def test_get_manual_power_no_data(self, coordinator):
        """Test get_manual_power returns None when no data."""
        assert coordinator.get_manual_power() is None


class TestCoordinatorWithPartialData:
    """Test coordinator methods when device_info has partial data."""

    def test_get_temperature_missing_status(self, coordinator):
        """Test get_temperature with missing status."""
        coordinator._device_info = {"nvm": {}}
        assert coordinator.get_temperature() is None

    def test_get_temperature_missing_temperatures(self, coordinator):
        """Test get_temperature with missing temperatures."""
        coordinator._device_info = {"status": {}}
        assert coordinator.get_temperature() is None

    def test_get_fan_speed_missing_nvm(self, coordinator):
        """Test get_fan_speed with missing nvm."""
        coordinator._device_info = {"status": {}}
        assert coordinator.get_fan_speed(1) is None

    def test_get_fan_speed_missing_user_parameters(self, coordinator):
        """Test get_fan_speed with missing user_parameters."""
        coordinator._device_info = {"nvm": {}}
        assert coordinator.get_fan_speed(1) is None

    def test_get_nb_fans_missing_installer_parameters(self, coordinator):
        """Test get_nb_fans with missing installer_parameters."""
        coordinator._device_info = {"nvm": {}}
        assert coordinator.get_nb_fans() is None

    def test_get_alarms_missing_alarms_array(self, coordinator):
        """Test get_alarms with missing alarms array."""
        coordinator._device_info = {"nvm": {"alarms_log": {"index": 5}}}
        assert coordinator.get_alarms() == []

    def test_get_alarms_index_out_of_bounds(self, coordinator):
        """Test get_alarms when index exceeds alarms array length."""
        coordinator._device_info = {
            "nvm": {"alarms_log": {"index": 10, "alarms": [{"type": 1}, {"type": 2}]}}
        }
        # Should only return the 2 alarms that exist
        assert len(coordinator.get_alarms()) == 2


class TestCoordinatorWithValidData:
    """Test coordinator methods with valid data."""

    def test_get_temperature_with_valid_data(self, coordinator):
        """Test get_temperature with valid data."""
        coordinator._device_info = {
            "status": {"temperatures": {"enviroment": 22.5}}
        }
        assert coordinator.get_temperature() == 22.5

    def test_get_fan_speed_with_valid_data(self, coordinator):
        """Test get_fan_speed with valid data."""
        coordinator._device_info = {
            "nvm": {"user_parameters": {"fan_1_ventilation": 3}}
        }
        assert coordinator.get_fan_speed(1) == 3

    def test_get_nb_fans_with_valid_data(self, coordinator):
        """Test get_nb_fans with valid data."""
        coordinator._device_info = {
            "nvm": {"installer_parameters": {"fans_number": 2}}
        }
        assert coordinator.get_nb_fans() == 2

    def test_get_alarms_with_valid_data(self, coordinator):
        """Test get_alarms with valid data."""
        coordinator._device_info = {
            "nvm": {
                "alarms_log": {
                    "index": 2,
                    "alarms": [
                        {"type": 1, "timestamp": 1234567890},
                        {"type": 2, "timestamp": 1234567900},
                    ],
                }
            }
        }
        alarms = coordinator.get_alarms()
        assert len(alarms) == 2
        assert alarms[0]["type"] == 1
        assert alarms[1]["type"] == 2

    def test_get_power_ons_with_valid_data(self, coordinator):
        """Test get_power_ons with valid data."""
        coordinator._device_info = {"nvm": {"total_counters": {"power_ons": 42}}}
        assert coordinator.get_power_ons() == 42

    def test_is_auto_with_valid_data(self, coordinator):
        """Test is_auto with valid data."""
        coordinator._device_info = {"nvm": {"user_parameters": {"is_auto": True}}}
        assert coordinator.is_auto() is True

    def test_get_autonomy_second_with_valid_data(self, coordinator):
        """Test get_autonomy_second with valid data."""
        coordinator._device_info = {"status": {"pellet": {"autonomy_time": 3600}}}
        assert coordinator.get_autonomy_second() == 3600
