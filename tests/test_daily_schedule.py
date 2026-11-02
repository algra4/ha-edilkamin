"""Tests for read-only daily schedules; no real cloud or stove commands."""

import asyncio
from copy import deepcopy
from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import SensorDeviceClass
import pytest

from custom_components.edilkamin.schedule import (
    EdilkaminDailyScheduleSensor,
    schedule_periods,
)
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


def test_periods_request_example():
    assert schedule_periods([0, 0, 1, 1, 2, 2], is_auto=True) == [
        {"start": "00:00", "end": "01:00", "mode": "off"},
        {"start": "01:00", "end": "02:00", "mode": "economy"},
        {"start": "02:00", "end": "03:00", "mode": "comfort"},
    ]


@pytest.mark.parametrize(
    ("is_auto", "value", "mode"),
    [
        (True, 0, "off"),
        (True, 1, "economy"),
        (True, 2, "comfort"),
        (False, 0, "off"),
        (False, 1, "power_1"),
        (False, 2, "power_2"),
        (False, 3, "power_3"),
        (False, 4, "power_4"),
        (False, 5, "power_5"),
    ],
)
def test_periods_full_day_and_modes(coordinator, is_auto, value, mode):
    coordinator.data["nvm"]["user_parameters"]["is_auto"] = is_auto
    key = "temperature_ranges" if is_auto else "power_ranges"
    coordinator.data["nvm"]["chrono"][key] = [value] * 336
    sensor = EdilkaminDailyScheduleSensor(coordinator)
    assert sensor.extra_state_attributes["periods"] == [
        {"start": "00:00", "end": "24:00", "mode": mode},
    ]
    assert sensor.extra_state_attributes["slots"] == [value] * 48


def test_periods_half_hour_boundaries_and_separated_runs():
    assert schedule_periods([0] + [2] * 46 + [0], is_auto=True) == [
        {"start": "00:00", "end": "00:30", "mode": "off"},
        {"start": "00:30", "end": "23:30", "mode": "comfort"},
        {"start": "23:30", "end": "24:00", "mode": "off"},
    ]


def test_periods_alternating_slots_cover_each_half_hour():
    periods = schedule_periods([0, 1] * 24, is_auto=True)
    assert len(periods) == 48
    assert periods[0] == {"start": "00:00", "end": "00:30", "mode": "off"}
    assert periods[-1] == {"start": "23:30", "end": "24:00", "mode": "economy"}
    for index, period in enumerate(periods):
        assert period["start"] == f"{index // 2:02d}:{index % 2 * 30:02d}"
        assert period["end"] == f"{(index + 1) // 2:02d}:{(index + 1) % 2 * 30:02d}"
        if index:
            assert periods[index - 1]["end"] == period["start"]


def test_manual_periods_keep_different_power_levels_separate():
    assert schedule_periods([0, 1, 1, 5, 5, 2], is_auto=False) == [
        {"start": "00:00", "end": "00:30", "mode": "off"},
        {"start": "00:30", "end": "01:30", "mode": "power_1"},
        {"start": "01:30", "end": "02:30", "mode": "power_5"},
        {"start": "02:30", "end": "03:00", "mode": "power_2"},
    ]


def test_periods_use_selected_day_and_ignore_chrono_enablement(coordinator):
    saved = [0, 0, 1, 1, 2, 2] + [0] * 42
    coordinator.data["nvm"]["chrono"]["temperature_ranges"][48:96] = saved
    original = deepcopy(coordinator.data)
    sensor = EdilkaminDailyScheduleSensor(coordinator)
    now = datetime(2026, 10, 20, 12, tzinfo=ZoneInfo("Europe/Berlin"))
    with patch("custom_components.edilkamin.schedule.dt_util.now", return_value=now):
        enabled = sensor.extra_state_attributes
        assert coordinator.data == original
        coordinator.data["nvm"]["chrono"]["is_active"] = False
        disabled = sensor.extra_state_attributes
    assert enabled["slots"] == disabled["slots"] == saved
    assert (
        enabled["periods"]
        == disabled["periods"]
        == [
            {"start": "00:00", "end": "01:00", "mode": "off"},
            {"start": "01:00", "end": "02:00", "mode": "economy"},
            {"start": "02:00", "end": "03:00", "mode": "comfort"},
            {"start": "03:00", "end": "24:00", "mode": "off"},
        ]
    )
    assert disabled["chrono_active"] is False
    enabled["periods"][0]["end"] = "12:00"
    assert disabled["periods"][0]["end"] == "01:00"


@pytest.mark.parametrize(("month", "day"), [(3, 29), (10, 25)])
def test_periods_use_wall_clock_times_on_dst_days(coordinator, month, day):
    coordinator.data["nvm"]["chrono"]["temperature_ranges"] = ([1] * 6 + [0] * 42) * 7
    sensor = EdilkaminDailyScheduleSensor(coordinator)
    now = datetime(2026, month, day, 12, tzinfo=ZoneInfo("Europe/Berlin"))
    with patch("custom_components.edilkamin.schedule.dt_util.now", return_value=now):
        assert sensor.extra_state_attributes["periods"] == [
            {"start": "00:00", "end": "03:00", "mode": "economy"},
            {"start": "03:00", "end": "24:00", "mode": "off"},
        ]
