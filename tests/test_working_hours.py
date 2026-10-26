"""Lifetime counters: use the real HA entity classes, with offline API data."""

from unittest.mock import Mock

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTime
import pytest

from custom_components.edilkamin.const import DOMAIN
from custom_components.edilkamin.coordinator import EdilkaminCoordinator
from custom_components.edilkamin.sensor import (
    EdilkaminWorkingHoursSensor,
    async_setup_entry,
)


@pytest.fixture
def coordinator():
    """Construct without networking; all counters below are synthetic."""
    instance = object.__new__(EdilkaminCoordinator)
    instance._mac_address = "test-device"
    instance.last_update_success = True
    instance._device_info = {
        "nvm": {
            "total_counters": {
                f"p{power}_working_time": power * 10 for power in range(1, 6)
            },
            "service_counters": {"p1_working_time": 999},
        }
    }
    return instance


@pytest.mark.parametrize("power", [None, 1, 2, 3, 4, 5])
def test_values_and_metadata(coordinator, power):
    sensor = EdilkaminWorkingHoursSensor(coordinator, power)
    assert sensor.native_value == (150 if power is None else power * 10)
    assert sensor.available
    assert sensor.device_class == SensorDeviceClass.DURATION
    assert sensor.native_unit_of_measurement == UnitOfTime.HOURS
    assert sensor.state_class == SensorStateClass.TOTAL_INCREASING
    suffix = "total" if power is None else f"p{power}"
    assert sensor.unique_id == f"test-device_{suffix}_working_hours"
    assert sensor.device_info == {"identifiers": {(DOMAIN, "test-device")}}


@pytest.mark.parametrize(
    "value", [None, True, False, -1, "12", 1.5, float("nan"), float("inf"), [], {}]
)
def test_invalid_counter_is_not_zero_or_partial_sum(coordinator, value):
    coordinator._device_info["nvm"]["total_counters"]["p3_working_time"] = value
    for power in (None, 3):
        sensor = EdilkaminWorkingHoursSensor(coordinator, power)
        assert sensor.native_value is None
        assert not sensor.available
    assert EdilkaminWorkingHoursSensor(coordinator, 1).native_value == 10


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        {},
        {"nvm": None},
        {"nvm": []},
        {"nvm": {"total_counters": None}},
        {"nvm": {"total_counters": []}},
    ],
)
def test_missing_or_malformed_sections(coordinator, data):
    coordinator._device_info = data
    assert coordinator.get_working_hours() is None
    assert coordinator.get_working_hours(1) is None


def test_missing_level_zero_and_recovery(coordinator):
    sensor = EdilkaminWorkingHoursSensor(coordinator)
    counters = coordinator._device_info["nvm"]["total_counters"]
    del counters["p5_working_time"]
    assert sensor.native_value is None
    assert not sensor.available
    counters["p5_working_time"] = 0
    assert sensor.native_value == 100
    assert sensor.available
    for key in counters:
        counters[key] = 0
    assert sensor.native_value == 0
    assert sensor.available


def test_update_failure_and_service_reset(coordinator):
    sensor = EdilkaminWorkingHoursSensor(coordinator)
    coordinator._device_info["nvm"]["service_counters"]["p1_working_time"] = 0
    assert sensor.native_value == 150
    coordinator.last_update_success = False
    assert not sensor.available
    coordinator.last_update_success = True
    coordinator._device_info["nvm"]["total_counters"]["p1_working_time"] += 1
    assert sensor.native_value == 151
    assert sensor.available


@pytest.mark.parametrize("power", [0, 6, True, "1", 1.0])
def test_invalid_power(coordinator, power):
    assert coordinator.get_working_hours(power) is None


@pytest.mark.asyncio
async def test_setup_registers_six_distinct_entities():
    coordinator = Mock()
    coordinator.get_mac_address.return_value = "test-device"
    coordinator.get_temperatures.return_value = {}
    coordinator.get_nb_fans.return_value = 1
    hass = Mock()
    coordinator.pellet = None
    hass.data = {DOMAIN: {"coordinators": {"test": coordinator}}}
    add_entities = Mock()
    await async_setup_entry(hass, Mock(entry_id="test"), add_entities)
    sensors = [
        entity
        for entity in add_entities.call_args.args[0]
        if isinstance(entity, EdilkaminWorkingHoursSensor)
    ]
    assert len(sensors) == 6
    assert len({sensor.unique_id for sensor in sensors}) == 6
