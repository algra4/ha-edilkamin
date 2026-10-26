"""Offline tests using HA 2025.5 runtime, Store, flow and entity platforms."""

import asyncio
from copy import deepcopy
from datetime import timedelta
import logging
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry,
    device_registry,
    entity_platform,
    entity_registry,
    frame,
)
from homeassistant.helpers.storage import Store
from homeassistant.util.file import WriteError
import pytest
import pytest_asyncio
import voluptuous as vol
from voluptuous_serialize import convert

from custom_components.edilkamin import (
    async_setup_entry,
    async_unload_entry,
)
from custom_components.edilkamin.binary_sensor import (
    EdilkaminPelletIncompleteSensor,
    async_setup_entry as setup_binary,
)
from custom_components.edilkamin.config_flow import ConfigFlow
from custom_components.edilkamin.const import DOMAIN
from custom_components.edilkamin.coordinator import EdilkaminCoordinator
from custom_components.edilkamin.pellet import (
    COEFFICIENTS,
    ENABLED,
    PelletEstimate,
    coefficient,
)
from custom_components.edilkamin.sensor import (
    EdilkaminPelletSensor,
    async_setup_entry as setup_sensors,
)

OPTIONS = {ENABLED: True, COEFFICIENTS[0]: 0.5, COEFFICIENTS[1]: 1.25}


@pytest_asyncio.fixture
async def ha(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    frame.async_setup(hass)
    hass.config_entries = ConfigEntries(hass, {})
    await area_registry.async_load(hass)
    await entity_registry.async_load(hass)
    await device_registry.async_load(hass)
    yield hass
    await hass.async_stop()


def readings(coordinator, values):
    coordinator._device_info = {
        "nvm": {
            "total_counters": {
                f"p{i}_working_time": value for i, value in enumerate(values, 1)
            }
        }
    }


async def runtime(hass, entry_id="one", options=None):
    coordinator = EdilkaminCoordinator(hass, "offline", "offline", entry_id)
    coordinator.pellet = PelletEstimate(hass, entry_id)
    await coordinator.pellet.async_load(OPTIONS if options is None else options)
    return coordinator


@pytest.mark.parametrize(
    "value", [0, -1, True, False, "nan", "inf", "-inf", [], {}, "bad"]
)
def test_invalid_rate(value):
    with pytest.raises(vol.Invalid):
        coefficient(value)


@pytest.mark.parametrize("value", [None, ""])
def test_unknown_rate(value):
    assert coefficient(value) is None


@pytest.mark.asyncio
async def test_options_ui(ha):
    flow = ConfigFlow.async_get_options_flow(None)
    flow.hass = ha
    flow.handler = "entry"
    entry = SimpleNamespace(options={}, entry_id="entry")
    with patch.object(
        type(ha.config_entries), "async_get_known_entry", return_value=entry
    ):
        result = await flow.async_step_init()
        assert result["type"] == "form"
        schema = result["data_schema"]
        assert schema({}) == {ENABLED: False}
        for bad in (0, -1, "nan", "inf", True):
            result = await flow.async_step_init({ENABLED: True, COEFFICIENTS[0]: bad})
            assert result["errors"] == {"base": "invalid_coefficient"}
        result = await flow.async_step_init(
            {ENABLED: True, COEFFICIENTS[0]: "0.75", COEFFICIENTS[1]: ""}
        )
        assert result["type"] == "create_entry"
        assert result["data"][COEFFICIENTS[0]] == 0.75
        assert result["data"][COEFFICIENTS[1]] is None
        assert all(result["data"][key] is None for key in COEFFICIENTS[2:])


@pytest.mark.asyncio
async def test_baseline_math_unknown_and_sticky(ha):
    c = await runtime(ha)
    readings(c, [100, 200, 300, 400, 500])
    await c.pellet.async_update(c)
    assert c.pellet.state["kg"] == 0
    assert not c.pellet.incomplete
    readings(c, [102, 204, 300, 400, 500])
    await c.pellet.async_update(c)
    assert c.pellet.state["kg"] == 6
    assert not c.pellet.incomplete  # unknown powers with zero delta are fine
    readings(c, [102, 204, 301, 401, 501])
    await c.pellet.async_update(c)
    assert c.pellet.state["kg"] == 6
    assert set(c.pellet.state["reasons"]) == {
        "p3_uncalibrated",
        "p4_uncalibrated",
        "p5_uncalibrated",
    }
    await c.pellet.async_update(c)
    assert c.pellet.incomplete


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [None, True, -1, "3", 2.0, [], {}])
async def test_missing_malformed_and_recovery(ha, bad):
    c = await runtime(ha)
    readings(c, [10, 10, 10, 10, 10])
    await c.pellet.async_update(c)
    readings(c, [bad, 12, 10, 10, 10])
    await c.pellet.async_update(c)
    assert c.pellet.state["kg"] == 2.5
    assert c.pellet.state["previous"][0] == 10
    assert not EdilkaminPelletSensor(c).available
    readings(c, [14, 12, 10, 10, 10])
    await c.pellet.async_update(c)
    assert c.pellet.state["kg"] == 4.5
    c.last_update_success = True
    assert EdilkaminPelletSensor(c).available
    assert not c.pellet.incomplete


@pytest.mark.asyncio
async def test_initial_missing_is_not_zero(ha):
    c = await runtime(ha)
    readings(c, [None, 0, 0, 0, 0])
    await c.pellet.async_update(c)
    readings(c, [500, 0, 0, 0, 0])
    await c.pellet.async_update(c)
    assert c.pellet.state["kg"] == 0


@pytest.mark.asyncio
async def test_reset_restart_and_downtime_actual_store(ha):
    c = await runtime(ha)
    readings(c, [10, 20, 0, 0, 0])
    await c.pellet.async_update(c)
    readings(c, [12, 22, 0, 0, 0])
    await c.pellet.async_update(c)
    await c.pellet.async_flush()
    # New Store and runtime: no RestoreEntity or mocked storage.
    restored = await runtime(ha)
    assert restored.pellet.state["kg"] == 3.5
    readings(restored, [14, 24, 0, 0, 0])
    await restored.pellet.async_update(restored)
    assert restored.pellet.state["kg"] == 7
    readings(restored, [1, 2, 0, 0, 0])
    await restored.pellet.async_update(restored)
    assert restored.pellet.state["kg"] == 7
    assert restored.pellet.incomplete
    readings(restored, [2, 3, 0, 0, 0])
    await restored.pellet.async_update(restored)
    assert restored.pellet.state["kg"] == 8.75
    again = await runtime(ha)
    assert again.pellet.incomplete
    assert set(again.pellet.state["reasons"]) == {
        "p1_counter_reset",
        "p2_counter_reset",
    }
    assert (await Store(ha, 1, "edilkamin_pellet_one").async_load())["kg"] == 8.75


@pytest.mark.asyncio
async def test_option_boundary_and_disabled_gap(ha):
    c = await runtime(ha)
    readings(c, [10, 0, 0, 0, 0])
    await c.pellet.async_update(c)
    readings(c, [12, 0, 0, 0, 0])
    await c.pellet.async_update(c)
    changed = {**OPTIONS, COEFFICIENTS[0]: 2}
    await c.pellet.async_configure(changed)
    readings(c, [20, 0, 0, 0, 0])
    await c.pellet.async_update(c)
    assert c.pellet.state["kg"] == 1
    assert c.pellet.state["reasons"] == ["calibration_gap"]
    readings(c, [21, 0, 0, 0, 0])
    await c.pellet.async_update(c)
    assert c.pellet.state["kg"] == 3
    await c.pellet.async_configure({**changed, ENABLED: False})
    readings(c, [30, 0, 0, 0, 0])
    await c.pellet.async_update(c)
    await c.pellet.async_flush()
    restored = await runtime(ha, options=changed)
    readings(restored, [40, 0, 0, 0, 0])
    await restored.pellet.async_update(restored)
    assert restored.pellet.state["kg"] == 3
    readings(restored, [41, 0, 0, 0, 0])
    await restored.pellet.async_update(restored)
    assert restored.pellet.state["kg"] == 5
    assert restored.pellet.incomplete


@pytest.mark.asyncio
async def test_all_five_calibrated_rates(ha):
    options = {
        ENABLED: True,
        **{key: (i + 1) / 2 for i, key in enumerate(COEFFICIENTS)},
    }
    c = await runtime(ha, options=options)
    readings(c, [100] * 5)
    await c.pellet.async_update(c)
    readings(c, [100 + i for i in range(1, 6)])
    await c.pellet.async_update(c)
    assert c.pellet.state["kg"] == sum(i * (i / 2) for i in range(1, 6))
    assert not c.pellet.incomplete


@pytest.mark.asyncio
async def test_option_transaction_waits_for_old_coefficient_write(ha):
    c = await runtime(ha)
    readings(c, [10, 0, 0, 0, 0])
    await c.pellet.async_update(c)
    readings(c, [12, 0, 0, 0, 0])
    entered, release = asyncio.Event(), asyncio.Event()
    save = c.pellet.store.async_save

    async def delayed(state):
        entered.set()
        await release.wait()
        await save(state)

    changed = {**OPTIONS, COEFFICIENTS[0]: 4}
    with patch.object(c.pellet.store, "async_save", side_effect=delayed):
        update = asyncio.create_task(c.pellet.async_update(c))
        await entered.wait()
        configure = asyncio.create_task(c.pellet.async_configure(changed))
        await asyncio.sleep(0)
        assert not configure.done()
        release.set()
        await asyncio.gather(update, configure)
    restored = await runtime(ha, options=changed)
    assert restored.pellet.state["kg"] == 1
    assert restored.pellet.state["previous"] == [None] * 5
    assert restored.pellet.state["reasons"] == ["calibration_gap"]


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_storage_race_close_and_failure(ha, cancel):
    c = await runtime(ha)
    readings(c, [10, 0, 0, 0, 0])
    await c.pellet.async_update(c)
    readings(c, [12, 0, 0, 0, 0])
    entered, release = asyncio.Event(), asyncio.Event()
    save = c.pellet.store.async_save

    async def delayed(state):
        entered.set()
        await release.wait()
        await save(state)

    with patch.object(c.pellet.store, "async_save", side_effect=delayed):
        update = asyncio.create_task(c.pellet.async_update(c))
        await entered.wait()
        if cancel:
            update.cancel()
        close = asyncio.create_task(c.pellet.async_flush())
        await asyncio.sleep(0)
        assert not close.done()
        assert c.pellet.state["kg"] == 0
        release.set()
        results = await asyncio.gather(update, close, return_exceptions=True)
        if cancel:
            assert isinstance(results[0], asyncio.CancelledError)
        else:
            assert results[0] is None
        assert results[1] is None
    readings(c, [20, 0, 0, 0, 0])
    await c.pellet.async_update(c)  # late old coordinator must not overwrite Store
    restored = await runtime(ha)
    assert restored.pellet.state["kg"] == 1
    readings(restored, [14, 0, 0, 0, 0])
    before = deepcopy(restored.pellet.state)
    with (
        patch.object(restored.pellet.store, "async_save", side_effect=OSError("disk")),
        pytest.raises(OSError, match="disk"),
    ):
        await restored.pellet.async_update(restored)
    assert restored.pellet.state == before
    await restored.pellet.async_update(restored)
    assert restored.pellet.state["kg"] == 2


@pytest.mark.asyncio
async def test_multi_device_and_disabled_default(ha):
    a, b = await runtime(ha, "a"), await runtime(ha, "b", {})
    for c in (a, b):
        readings(c, [10, 0, 0, 0, 0])
        await c.pellet.async_update(c)
        readings(c, [12, 0, 0, 0, 0])
        await c.pellet.async_update(c)
    assert a.pellet.state["kg"] == 1
    assert b.pellet.state["kg"] == 0
    assert not b.pellet.enabled
    assert a.pellet.store.key != b.pellet.store.key
    assert EdilkaminPelletSensor(a).unique_id != EdilkaminPelletSensor(b).unique_id


@pytest.mark.asyncio
async def test_coordinator_fail_recover_without_extra_poll(ha):
    c = await runtime(ha)
    readings(c, [10, 0, 0, 0, 0])
    data = c._device_info
    with patch.object(
        c, "update_device_information", AsyncMock(return_value=data)
    ) as fetch:
        await c.async_refresh()
        assert fetch.await_count == 1
        data["nvm"]["total_counters"]["p1_working_time"] = 12
        fetch.side_effect = OSError
        await c.async_refresh()
        assert not c.last_update_success
        assert c.pellet.state["kg"] == 0
        fetch.side_effect = None
        await c.async_refresh()
        assert c.last_update_success
        assert c.pellet.state["kg"] == 1
        assert fetch.await_count == 3
    await c.async_shutdown()


@pytest.mark.asyncio
async def test_swallowed_store_error_is_detected(ha):
    c = await runtime(ha)
    readings(c, [10, 0, 0, 0, 0])
    await c.pellet.async_update(c)
    readings(c, [12, 0, 0, 0, 0])
    with (
        patch.object(
            c.pellet.store, "_async_write_data", side_effect=WriteError("disk full")
        ),
        pytest.raises(OSError, match="persisted"),
    ):
        await c.pellet.async_update(c)
    assert c.pellet.state["kg"] == 0
    await c.pellet.async_update(c)
    assert c.pellet.state["kg"] == 1


@pytest.mark.asyncio
async def test_option_change_after_restart_rebaselines(ha):
    c = await runtime(ha)
    readings(c, [10, 0, 0, 0, 0])
    await c.pellet.async_update(c)
    await c.pellet.async_flush()
    changed = {**OPTIONS, COEFFICIENTS[0]: 3}
    restored = await runtime(ha, options=changed)
    readings(restored, [20, 0, 0, 0, 0])
    await restored.pellet.async_update(restored)
    assert restored.pellet.state["kg"] == 0
    assert restored.pellet.state["reasons"] == ["calibration_gap"]
    readings(restored, [21, 0, 0, 0, 0])
    await restored.pellet.async_update(restored)
    assert restored.pellet.state["kg"] == 3


@pytest.mark.asyncio
async def test_corrupt_storage_fails_closed(ha):
    await Store(ha, 1, "edilkamin_pellet_bad").async_save({"kg": "not numeric"})
    with pytest.raises(ValueError, match="Invalid pellet estimate storage"):
        await runtime(ha, "bad")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content", ["{}", "null", "[]", '{"version":1,"data":null}', "{broken"]
)
async def test_corrupt_json_is_not_renamed_and_replaced(ha, content):
    estimator = PelletEstimate(ha, "corrupt_json")
    path = Path(estimator.store.path)

    def write_corrupt():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    await ha.async_add_executor_job(write_corrupt)
    with pytest.raises(ValueError, match=r"storage|Expecting"):
        await estimator.async_load(OPTIONS)
    assert await ha.async_add_executor_job(path.read_text) == content


@pytest.mark.asyncio
async def test_options_while_unloaded_preserve_disable_boundary(ha):
    c = await runtime(ha, "entry")
    readings(c, [10, 0, 0, 0, 0])
    await c.pellet.async_update(c)
    readings(c, [12, 0, 0, 0, 0])
    await c.pellet.async_update(c)
    await c.pellet.async_flush()
    flow = ConfigFlow.async_get_options_flow(None)
    flow.hass = ha
    flow.handler = "entry"
    entry = SimpleNamespace(options=OPTIONS, entry_id="entry")
    with patch.object(
        type(ha.config_entries), "async_get_known_entry", return_value=entry
    ):
        disabled = await flow.async_step_init({**OPTIONS, ENABLED: False})
        entry.options = disabled["data"]
        enabled = await flow.async_step_init(OPTIONS)
    assert enabled["type"] == "create_entry"
    restored = await runtime(ha, "entry", enabled["data"])
    readings(restored, [30, 0, 0, 0, 0])
    await restored.pellet.async_update(restored)
    assert restored.pellet.state["kg"] == 1
    assert not restored.pellet.incomplete


@pytest.mark.asyncio
async def test_fresh_homeassistant_restart(ha):
    """Restore in a new HA instance, not a cached Store manager."""
    c = await runtime(ha)
    readings(c, [10, 0, 0, 0, 0])
    await c.pellet.async_update(c)
    readings(c, [12, 0, 0, 0, 0])
    await c.pellet.async_update(c)
    await c.pellet.async_flush()
    await ha.async_stop()
    restarted = HomeAssistant(ha.config.config_dir)
    frame.async_setup(restarted)
    try:
        restored = await runtime(restarted)
        assert restored.pellet.state["kg"] == 1
        readings(restored, [16, 0, 0, 0, 0])
        await restored.pellet.async_update(restored)
        assert restored.pellet.state["kg"] == 3
        await restored.pellet.async_update(restored)
        assert restored.pellet.state["kg"] == 3
        await restored.pellet.async_flush()
    finally:
        await restarted.async_stop()


@pytest.mark.asyncio
async def test_entry_setup_options_reload_and_multi_device(ha):
    """Exercise integration entry hooks with HA ConfigEntry and real Store.

    Forwarding/unloading is mocked to avoid existing command-capable platforms;
    the new entities' real EntityPlatform lifecycle is exercised separately.
    """
    entries = []
    data = {"nvm": {"total_counters": {f"p{i}_working_time": 10 for i in range(1, 6)}}}
    with (
        patch.object(
            EdilkaminCoordinator,
            "update_device_information",
            AsyncMock(return_value=data),
        ),
        patch.object(
            type(ha.config_entries), "async_forward_entry_setups", AsyncMock()
        ),
        patch.object(
            type(ha.config_entries),
            "async_unload_platforms",
            AsyncMock(return_value=True),
        ),
    ):
        for name in ("device_a", "device_b"):
            entry = ConfigEntry(
                domain=DOMAIN,
                entry_id=name,
                data={
                    "mac_address": name,
                    "username": "offline",
                    "password": "offline",
                },
                options=OPTIONS,
                title=name,
                unique_id=name,
                version=2,
                minor_version=1,
                source="user",
                discovery_keys=MappingProxyType({}),
                subentries_data=None,
            )
            ha.config_entries._entries[entry.entry_id] = entry
            assert await async_setup_entry(ha, entry)
            entries.append(entry)
        for entry in entries:
            added = []
            await setup_sensors(ha, entry, added.extend)
            await setup_binary(ha, entry, added.extend)
            pellet_entities = [
                e
                for e in added
                if isinstance(
                    e, (EdilkaminPelletSensor, EdilkaminPelletIncompleteSensor)
                )
            ]
            assert len(pellet_entities) == 2
            assert all(
                e.device_info["identifiers"] == {(DOMAIN, entry.entry_id)}
                for e in pellet_entities
            )
        entry = entries[0]
        coordinator = ha.data[DOMAIN]["coordinators"][entry.entry_id]
        readings(coordinator, [12, 10, 10, 10, 10])
        await coordinator.pellet.async_update(coordinator)
        assert coordinator.pellet.state["kg"] == 1
        flow = ConfigFlow.async_get_options_flow(entry)
        flow.hass = ha
        flow.handler = entry.entry_id
        form = await flow.async_step_init()
        # This is serializable to the actual HA frontend's flow form schema.
        assert any(
            field["name"] == COEFFICIENTS[0] for field in convert(form["data_schema"])
        )
        updated = await flow.async_step_init({**OPTIONS, COEFFICIENTS[0]: 2})
        # Exercise the real ConfigEntries update listener dispatch.
        with patch.object(
            type(ha.config_entries), "async_reload", AsyncMock(return_value=True)
        ) as reload_entry:
            ha.config_entries.async_update_entry(entry, options=updated["data"])
            await ha.async_block_till_done()
            reload_entry.assert_awaited_once_with(entry.entry_id)
        assert coordinator.pellet.state["previous"] == [None] * 5
        assert coordinator.pellet.incomplete
        assert await async_unload_entry(ha, entry)
        assert coordinator.pellet.closed
        assert await async_setup_entry(ha, entry)
        restored = ha.data[DOMAIN]["coordinators"][entry.entry_id]
        assert restored is not coordinator
        assert restored.pellet.state["kg"] == 1
        assert restored.pellet.incomplete
        assert (
            ha.data[DOMAIN]["coordinators"][entries[1].entry_id].pellet.state["kg"] == 0
        )
        for entry in entries:
            assert await async_unload_entry(ha, entry)
        assert not ha.data[DOMAIN]["coordinators"]


@pytest.mark.asyncio
async def test_actual_ha_entity_lifecycle(ha):
    c = await runtime(ha)
    readings(c, [10, 0, 0, 0, 0])
    await c.pellet.async_update(c)
    c.last_update_success = True
    platforms = []
    for domain, entity in (
        ("sensor", EdilkaminPelletSensor(c)),
        ("binary_sensor", EdilkaminPelletIncompleteSensor(c)),
    ):
        platform = entity_platform.EntityPlatform(
            hass=ha,
            logger=logging.getLogger(__name__),
            domain=domain,
            platform_name="edilkamin",
            platform=None,
            scan_interval=timedelta(seconds=30),
            entity_namespace=None,
        )
        await platform.async_add_entities([entity])
        platforms.append(platform)
    assert ha.states.get("sensor.estimated_pellet_consumption").state == "0.0"
    diagnostic = ha.states.get("binary_sensor.pellet_estimate_incomplete")
    assert diagnostic.state == "off"
    readings(c, [12, 0, 0, 1, 0])
    await c.pellet.async_update(c)
    c.async_set_updated_data(c._device_info)
    await ha.async_block_till_done()
    assert ha.states.get("sensor.estimated_pellet_consumption").state == "1.0"
    assert ha.states.get(diagnostic.entity_id).state == "on"
    assert ha.states.get(diagnostic.entity_id).attributes["reasons"] == [
        "p4_uncalibrated"
    ]
    c.last_update_success = False
    c.async_update_listeners()
    await ha.async_block_till_done()
    assert ha.states.get("sensor.estimated_pellet_consumption").state == "unavailable"
    c.last_update_success = True
    c.async_update_listeners()
    await ha.async_block_till_done()
    assert ha.states.get("sensor.estimated_pellet_consumption").state == "1.0"
    for platform in platforms:
        await platform.async_reset()
    assert not c._listeners
    await c.async_shutdown()
    await c.pellet.async_flush()
