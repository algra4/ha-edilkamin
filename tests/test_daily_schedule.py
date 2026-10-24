"""Tests for read-only daily schedules; no real cloud or stove commands."""

import asyncio
from copy import deepcopy
from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import SensorDeviceClass
import pytest

from custom_components.edilkamin.schedule import EdilkaminDailyScheduleSensor
from custom_components.edilkamin.sensor import async_setup_entry


@pytest.fixture
def coordinator():
    result = Mock()
    result.get_mac_address.return_value = "00:11:22:33:44:55"
    result.get_nb_fans.return_value = 1
    result.get_temperatures.return_value = {}
    result.last_update_success = True
    result.data = {
        "nvm": {
            "chrono": {
                "is_active": True,
                "temperature_ranges": [day % 3 for day in range(7) for _ in range(48)],
                "power_ranges": [day % 6 for day in range(7) for _ in range(48)],
                "economy_temperature": 20,
                "comfort_temperature": 22,
            },
            "user_parameters": {"is_auto": True},
        }
    }
    return result


def test_metadata(coordinator):
    sensor = EdilkaminDailyScheduleSensor(coordinator)
    assert sensor.unique_id == "00:11:22:33:44:55_daily_schedule"
    assert sensor.name == "Daily schedule"
    assert sensor.device_class == SensorDeviceClass.ENUM
    assert sensor.options == ["enabled", "disabled"]
    assert sensor.device_info["identifiers"] == {("edilkamin", "00:11:22:33:44:55")}


@pytest.mark.parametrize("day", range(7))
@pytest.mark.parametrize("is_auto", [True, False])
def test_weekday_and_mode(coordinator, day, is_auto):
    coordinator.data["nvm"]["user_parameters"]["is_auto"] = is_auto
    sensor = EdilkaminDailyScheduleSensor(coordinator)
    now = datetime(2026, 10, 19 + day, 12, tzinfo=ZoneInfo("Europe/Berlin"))
    with patch("custom_components.edilkamin.schedule.dt_util.now", return_value=now):
        attributes = sensor.extra_state_attributes
    assert sensor.available
    assert sensor.native_value == "enabled"
    assert attributes["slots"] == [day % (3 if is_auto else 6)] * 48
    assert attributes["date"] == now.date().isoformat()
    assert attributes["is_auto"] is is_auto
    assert attributes["economy_temperature"] == 20
    assert attributes["comfort_temperature"] == 22


def test_disabled_chrono_keeps_program(coordinator):
    coordinator.data["nvm"]["chrono"]["is_active"] = False
    sensor = EdilkaminDailyScheduleSensor(coordinator)
    assert sensor.available
    assert sensor.native_value == "disabled"
    assert sensor.extra_state_attributes["chrono_active"] is False
    assert len(sensor.extra_state_attributes["slots"]) == 48


@pytest.mark.parametrize(
    "values",
    [
        None,
        [],
        [0] * 335,
        [0] * 337,
        "0" * 336,
        [True] * 336,
        ["1"] * 336,
        [-1] * 336,
        [3] * 336,
        [1.0] * 336,
    ],
)
def test_malformed_schedule_is_unavailable(coordinator, values):
    coordinator.data["nvm"]["chrono"]["temperature_ranges"] = values
    sensor = EdilkaminDailyScheduleSensor(coordinator)
    assert not sensor.available
    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


@pytest.mark.parametrize(
    "data",
    [
        None,
        {},
        {"nvm": None},
        {"nvm": {}},
        {"nvm": {"chrono": None, "user_parameters": {}}},
    ],
)
def test_missing_data_is_unavailable(coordinator, data):
    coordinator.data = data
    assert not EdilkaminDailyScheduleSensor(coordinator).available


@pytest.mark.parametrize("field", ["is_active", "is_auto"])
@pytest.mark.parametrize("value", [None, "false", 2, 0.0])
def test_invalid_mode_flags(coordinator, field, value):
    section = "chrono" if field == "is_active" else "user_parameters"
    coordinator.data["nvm"][section][field] = value
    assert not EdilkaminDailyScheduleSensor(coordinator).available


def test_cloud_failure_and_recovery(coordinator):
    sensor = EdilkaminDailyScheduleSensor(coordinator)
    coordinator.last_update_success = False
    assert not sensor.available
    coordinator.last_update_success = True
    assert sensor.available


def test_midnight_rollover_uses_ha_timezone(coordinator):
    coordinator.data["nvm"]["chrono"]["temperature_ranges"][288:] = [2] * 48
    sensor = EdilkaminDailyScheduleSensor(coordinator)
    zone = ZoneInfo("Europe/Berlin")
    with patch("custom_components.edilkamin.schedule.dt_util.DEFAULT_TIME_ZONE", zone):
        with patch(
            "custom_components.edilkamin.schedule.dt_util.now",
            return_value=datetime(2026, 10, 25, 23, 59, tzinfo=zone),
        ):
            sunday = sensor.extra_state_attributes
        with patch(
            "custom_components.edilkamin.schedule.dt_util.now",
            return_value=datetime(2026, 10, 26, 0, 0, tzinfo=zone),
        ):
            monday = sensor.extra_state_attributes
    assert sunday["slots"] == [2] * 48
    assert monday["slots"] == [0] * 48
    assert sunday["date"] == "2026-10-25"
    assert monday["date"] == "2026-10-26"
    assert monday["timezone"] == "Europe/Berlin"


@pytest.mark.parametrize(("month", "day"), [(3, 29), (10, 25)])
def test_dst_days_keep_wall_clock_slots(coordinator, month, day):
    sensor = EdilkaminDailyScheduleSensor(coordinator)
    now = datetime(2026, month, day, 12, tzinfo=ZoneInfo("Europe/Berlin"))
    with patch("custom_components.edilkamin.schedule.dt_util.now", return_value=now):
        assert len(sensor.extra_state_attributes["slots"]) == 48


def test_read_only_and_no_extra_requests(coordinator):
    original = deepcopy(coordinator.data)
    sensor = EdilkaminDailyScheduleSensor(coordinator)
    slots = sensor.extra_state_attributes["slots"]
    slots[0] = 5
    assert coordinator.data == original
    coordinator.async_request_refresh.assert_not_called()
    sensor.async_write_ha_state = Mock()
    sensor._handle_coordinator_update()
    sensor.async_write_ha_state.assert_called_once()


def test_setup_registers_sensor(coordinator):
    hass = Mock(data={"edilkamin": {"coordinator": coordinator}})
    add_entities = Mock()
    asyncio.run(async_setup_entry(hass, Mock(), add_entities))
    assert (
        sum(
            isinstance(entity, EdilkaminDailyScheduleSensor)
            for entity in add_entities.call_args.args[0]
        )
        == 1
    )
