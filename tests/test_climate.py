"""Tests for climate entity."""

from unittest.mock import AsyncMock, Mock

from homeassistant.components.climate import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
import pytest

from custom_components.edilkamin.climate import (
    FAN_MODES_MANAGED,
    FAN_PRESET_MODE_AUTO,
    PRESET_AUTO,
    PRESET_MODES,
    EdilkaminClimateEntity,
    async_setup_entry,
)
from custom_components.edilkamin.const import DOMAIN


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator instance."""
    coordinator = Mock()
    coordinator.get_mac_address = Mock(return_value="00:11:22:33:44:55")
    coordinator.async_add_listener = Mock()
    coordinator.async_refresh = AsyncMock()
    coordinator.get_temperature = Mock(return_value=20.5)
    coordinator.get_target_temperature = Mock(return_value=21.0)
    coordinator.get_fan_speed = Mock(return_value=3)
    coordinator.get_power_status = Mock(return_value=True)
    coordinator.is_auto = Mock(return_value=True)
    coordinator.get_manual_power = Mock(return_value=1)
    return coordinator


@pytest.fixture
def mock_api():
    """Create a mock API instance."""
    api = Mock()
    api.set_temperature = AsyncMock()
    api.set_fan_speed = AsyncMock()
    api.enable_power = AsyncMock()
    api.disable_power = AsyncMock()
    api.enable_auto_mode = AsyncMock()
    api.disable_auto_mode = AsyncMock()
    api.set_manual_power_level = AsyncMock()
    return api


class TestEdilkaminClimateEntity:
    """Test EdilkaminClimateEntity class."""

    def test_init(self, mock_api, mock_coordinator):
        """Test climate initialization and default attributes."""
        climate = EdilkaminClimateEntity(mock_api, mock_coordinator)

        assert climate.min_temp == 5
        assert climate.max_temp == 35
        assert climate._attr_min_temp == 5
        assert climate._attr_max_temp == 35
        assert climate._mac_address == "00:11:22:33:44:55"
        assert climate.unique_id == "00:11:22:33:44:55_climate"
        assert climate.temperature_unit == UnitOfTemperature.CELSIUS
        assert climate.fan_modes == FAN_MODES_MANAGED
        assert climate.hvac_mode == HVACMode.OFF
        assert climate.preset_modes == PRESET_MODES
        assert climate.preset_mode == PRESET_AUTO
        assert climate.name == "Edilkamin climate"
        assert climate.device_info == {
            "identifiers": {("edilkamin", "00:11:22:33:44:55")}
        }

    def test_supported_features(self, mock_api, mock_coordinator):
        """Test supported features."""
        climate = EdilkaminClimateEntity(mock_api, mock_coordinator)

        expected_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        assert climate.supported_features == expected_features

    @pytest.mark.asyncio
    async def test_async_set_temperature(self, mock_api, mock_coordinator):
        """Test setting target temperature."""
        climate = EdilkaminClimateEntity(mock_api, mock_coordinator)

        await climate.async_set_temperature(**{ATTR_TEMPERATURE: 22.5})

        mock_api.set_temperature.assert_awaited_once_with(22.5)
        mock_coordinator.async_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_set_temperature_without_temp(self, mock_api, mock_coordinator):
        """Test setting target temperature when temperature key is missing."""
        climate = EdilkaminClimateEntity(mock_api, mock_coordinator)

        await climate.async_set_temperature()

        mock_api.set_temperature.assert_not_called()
        mock_coordinator.async_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_set_fan_mode_numeric(self, mock_api, mock_coordinator):
        """Test setting fan mode to numeric speed."""
        climate = EdilkaminClimateEntity(mock_api, mock_coordinator)

        await climate.async_set_fan_mode("3")

        mock_api.set_fan_speed.assert_awaited_once_with("3")
        mock_coordinator.async_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_set_fan_mode_auto(self, mock_api, mock_coordinator):
        """Test setting fan mode to auto."""
        climate = EdilkaminClimateEntity(mock_api, mock_coordinator)

        await climate.async_set_fan_mode(FAN_PRESET_MODE_AUTO)

        mock_api.set_fan_speed.assert_awaited_once_with(6)
        mock_coordinator.async_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_heat(self, mock_api, mock_coordinator):
        """Test setting HVAC mode to HEAT."""
        climate = EdilkaminClimateEntity(mock_api, mock_coordinator)

        await climate.async_set_hvac_mode(HVACMode.HEAT)

        mock_api.enable_power.assert_awaited_once()
        mock_coordinator.async_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_off(self, mock_api, mock_coordinator):
        """Test setting HVAC mode to OFF."""
        climate = EdilkaminClimateEntity(mock_api, mock_coordinator)

        await climate.async_set_hvac_mode(HVACMode.OFF)

        mock_api.disable_power.assert_awaited_once()
        mock_coordinator.async_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode_unsupported(self, mock_api, mock_coordinator):
        """Test setting unsupported HVAC mode raises ValueError."""
        climate = EdilkaminClimateEntity(mock_api, mock_coordinator)

        with pytest.raises(ValueError, match="Unsupported HVAC mode"):
            await climate.async_set_hvac_mode(HVACMode.COOL)

    @pytest.mark.asyncio
    async def test_async_turn_on(self, mock_api, mock_coordinator):
        """Test turning on sets HVAC mode to HEAT."""
        climate = EdilkaminClimateEntity(mock_api, mock_coordinator)

        await climate.async_turn_on()

        mock_api.enable_power.assert_awaited_once()
        mock_coordinator.async_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_turn_off(self, mock_api, mock_coordinator):
        """Test turning off sets HVAC mode to OFF."""
        climate = EdilkaminClimateEntity(mock_api, mock_coordinator)

        await climate.async_turn_off()

        mock_api.disable_power.assert_awaited_once()
        mock_coordinator.async_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_auto(self, mock_api, mock_coordinator):
        """Test setting preset mode to Auto."""
        climate = EdilkaminClimateEntity(mock_api, mock_coordinator)

        await climate.async_set_preset_mode(PRESET_AUTO)

        mock_api.enable_auto_mode.assert_awaited_once()
        mock_coordinator.async_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_set_preset_mode_manual(self, mock_api, mock_coordinator):
        """Test setting preset mode to manual power level."""
        climate = EdilkaminClimateEntity(mock_api, mock_coordinator)

        await climate.async_set_preset_mode("Manual P3")

        mock_api.disable_auto_mode.assert_awaited_once()
        mock_api.set_manual_power_level.assert_awaited_once_with(3)
        mock_coordinator.async_refresh.assert_awaited_once()

    def test_handle_coordinator_update_auto(self, mock_api, mock_coordinator):
        """Test coordinator update handling in auto mode."""
        climate = EdilkaminClimateEntity(mock_api, mock_coordinator)
        climate.async_write_ha_state = Mock()

        climate._handle_coordinator_update()

        assert climate.current_temperature == 20.5
        assert climate.target_temperature == 21.0
        assert climate.fan_mode == "3"
        assert climate.hvac_mode == HVACMode.HEAT
        assert climate.preset_mode == PRESET_AUTO
        climate.async_write_ha_state.assert_called_once()

    def test_handle_coordinator_update_manual_and_fan_auto(
        self, mock_api, mock_coordinator
    ):
        """Test coordinator update handling with fan speed 6 and manual preset."""
        mock_coordinator.get_fan_speed.return_value = 6
        mock_coordinator.get_power_status.return_value = False
        mock_coordinator.is_auto.return_value = False
        mock_coordinator.get_manual_power.return_value = 2

        climate = EdilkaminClimateEntity(mock_api, mock_coordinator)
        climate.async_write_ha_state = Mock()

        climate._handle_coordinator_update()

        assert climate.fan_mode == FAN_PRESET_MODE_AUTO
        assert climate.hvac_mode == HVACMode.OFF
        assert climate.preset_mode == "Manual P2"

    def test_handle_coordinator_update_ignores_zero_temperature(
        self, mock_api, mock_coordinator
    ):
        """Test coordinator update ignores temperature of 0 or None."""
        mock_coordinator.get_temperature.return_value = 0

        climate = EdilkaminClimateEntity(mock_api, mock_coordinator)
        climate.async_write_ha_state = Mock()

        climate._handle_coordinator_update()

        assert climate.current_temperature is None


class TestClimateSetup:
    """Test async_setup_entry for climate platform."""

    @pytest.mark.asyncio
    async def test_async_setup_entry(self, mock_api, mock_coordinator):
        """Test setting up climate platform creates entities."""
        hass = Mock()
        entry = Mock()
        entry.entry_id = "test_entry"
        hass.data = {
            DOMAIN: {
                "test_entry": mock_api,
                "coordinators": {"test_entry": mock_coordinator},
            }
        }
        async_add_devices = Mock()

        await async_setup_entry(hass, entry, async_add_devices)

        async_add_devices.assert_called_once()
        devices = async_add_devices.call_args[0][0]
        assert len(devices) == 1
        assert isinstance(devices[0], EdilkaminClimateEntity)
