"""Offline races and damaged-store recovery with HA entry hooks and Store."""

import asyncio
from pathlib import Path
from types import MappingProxyType
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.storage import Store
import pytest

from custom_components.edilkamin import async_setup_entry, async_unload_entry
from custom_components.edilkamin.binary_sensor import EdilkaminPelletIncompleteSensor
from custom_components.edilkamin.config_flow import ConfigFlow
from custom_components.edilkamin.const import DOMAIN
from custom_components.edilkamin.coordinator import EdilkaminCoordinator
from custom_components.edilkamin.pellet import ENABLED, PelletEstimate
from custom_components.edilkamin.sensor import EdilkaminPelletSensor
from tests.test_pellet import OPTIONS, ha, readings, runtime  # noqa: F401


def entry_for(hass, name, options=OPTIONS):
    entry = ConfigEntry(
        domain=DOMAIN,
        entry_id=name,
        data={"mac_address": name, "username": "offline", "password": "offline"},
        options=options,
        title=name,
        unique_id=name,
        version=2,
        minor_version=1,
        source="user",
        discovery_keys=MappingProxyType({}),
        subentries_data=None,
    )
    hass.config_entries._entries[name] = entry
    return entry


def flow_for(hass, entry):
    flow = ConfigFlow.async_get_options_flow(entry)
    flow.hass = hass
    flow.handler = entry.entry_id
    return flow


async def finish_options(hass, entry, options):
    """Run the real options manager's synchronous entry update after the step."""
    flow = flow_for(hass, entry)
    result = await flow.async_step_init(options)
    if result["type"] == "create_entry":
        await hass.config_entries.options.async_finish_flow(flow, result)
    return result


def data_at(hours):
    return {
        "nvm": {
            "total_counters": {
                f"p{i}_working_time": hours if i == 1 else 0 for i in range(1, 6)
            }
        }
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("pause_at", ["load", "refresh"])
async def test_options_cannot_overtake_startup(ha, pause_at):  # noqa: F811
    entry = entry_for(ha, "raced")
    initial = await runtime(ha, entry.entry_id)
    readings(initial, [10, 0, 0, 0, 0])
    await initial.pellet.async_update(initial)
    readings(initial, [12, 0, 0, 0, 0])
    await initial.pellet.async_update(initial)
    await initial.pellet.async_flush()
    entered, release = asyncio.Event(), asyncio.Event()
    load = PelletEstimate.async_load

    async def delayed_load(self, options):
        if self.store.key.endswith("raced") and pause_at == "load":
            entered.set()
            await release.wait()
        await load(self, options)

    async def fetch(self):
        if self.get_mac_address() == "raced" and pause_at == "refresh":
            entered.set()
            await release.wait()
        return data_at(12)

    with (
        patch.object(PelletEstimate, "async_load", delayed_load),
        patch.object(EdilkaminCoordinator, "update_device_information", fetch),
        patch.object(
            type(ha.config_entries), "async_forward_entry_setups", AsyncMock()
        ),
        patch.object(
            type(ha.config_entries),
            "async_unload_platforms",
            AsyncMock(return_value=True),
        ),
        patch.object(
            type(ha.config_entries), "async_reload", AsyncMock(return_value=True)
        ),
    ):
        setup = asyncio.create_task(async_setup_entry(ha, entry))
        await asyncio.wait_for(entered.wait(), 2)
        disabled = asyncio.create_task(
            finish_options(ha, entry, {**OPTIONS, ENABLED: False})
        )
        await asyncio.sleep(0)
        assert not disabled.done()
        # A different entry is independent while the first is blocked.
        other = entry_for(ha, "other", {})
        assert await asyncio.wait_for(async_setup_entry(ha, other), 2)
        release.set()
        assert await asyncio.wait_for(setup, 2)
        assert (await asyncio.wait_for(disabled, 2))["type"] == "create_entry"
        await ha.async_block_till_done()
        c = ha.data[DOMAIN]["coordinators"][entry.entry_id]
        assert not c.pellet.enabled
        readings(c, [30, 0, 0, 0, 0])
        await c.pellet.async_update(c)
        saved = await Store(ha, 1, "edilkamin_pellet_raced").async_load()
        assert saved["kg"] == 1
        assert saved["previous"] == [None] * 5
        assert not saved["settings"][ENABLED]
        assert await async_unload_entry(ha, entry)
        assert await async_unload_entry(ha, other)


@pytest.mark.asyncio
async def test_unloaded_options_and_setup_share_boundary(ha):  # noqa: F811
    entry = entry_for(ha, "unloaded")
    initial = await runtime(ha, entry.entry_id)
    readings(initial, [10, 0, 0, 0, 0])
    await initial.pellet.async_update(initial)
    readings(initial, [12, 0, 0, 0, 0])
    await initial.pellet.async_update(initial)
    await initial.pellet.async_flush()
    entered, release = asyncio.Event(), asyncio.Event()
    original = PelletEstimate.async_load
    calls = 0

    async def delayed_load(self, options):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            await release.wait()
        await original(self, options)

    with (
        patch.object(PelletEstimate, "async_load", delayed_load),
        patch.object(
            EdilkaminCoordinator,
            "update_device_information",
            AsyncMock(return_value=data_at(30)),
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
        disable = asyncio.create_task(
            finish_options(ha, entry, {**OPTIONS, ENABLED: False})
        )
        await asyncio.wait_for(entered.wait(), 2)
        setup = asyncio.create_task(async_setup_entry(ha, entry))
        await asyncio.sleep(0)
        assert not setup.done()
        release.set()
        assert (await asyncio.wait_for(disable, 2))["type"] == "create_entry"
        assert await asyncio.wait_for(setup, 2)
        c = ha.data[DOMAIN]["coordinators"][entry.entry_id]
        assert not c.pellet.enabled
        assert c.pellet.state["kg"] == 1
        assert c.pellet.state["previous"] == [None] * 5
        assert await async_unload_entry(ha, entry)


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_enabled", [False, True])
@pytest.mark.parametrize(
    "corruption",
    [
        b"{broken",
        b"{}",
        b'{"version":2,"data":{}}',
        b'{"version":1,"data":{"kg":"broken"}}',
        b'{"version":1,"data":{"kg":' + b"9" * 400 + b"}}",
        b'{"version":1,"data":{"kg":' + b"9" * 5000 + b"}}",
    ],
)
async def test_corrupt_store_isolated_disable_restore_and_reenable(
    ha,  # noqa: F811
    initial_enabled,
    corruption,
):
    entry = entry_for(ha, "damaged", {**OPTIONS, ENABLED: initial_enabled})
    original = await runtime(ha, entry.entry_id)
    readings(original, [10, 0, 0, 0, 0])
    await original.pellet.async_update(original)
    readings(original, [12, 0, 0, 0, 0])
    await original.pellet.async_update(original)
    await original.pellet.async_flush()
    path = Path(original.pellet.store.path)
    backup = await ha.async_add_executor_job(path.read_bytes)
    await ha.async_add_executor_job(path.write_bytes, corruption)

    with (
        patch.object(
            EdilkaminCoordinator,
            "update_device_information",
            AsyncMock(return_value=data_at(30)),
        ) as fetch,
        patch.object(
            type(ha.config_entries), "async_forward_entry_setups", AsyncMock()
        ),
        patch.object(
            type(ha.config_entries),
            "async_unload_platforms",
            AsyncMock(return_value=True),
        ),
        patch.object(
            type(ha.config_entries), "async_reload", AsyncMock(return_value=True)
        ),
    ):
        assert await async_setup_entry(ha, entry)
        c = ha.data[DOMAIN]["coordinators"][entry.entry_id]
        assert c.pellet is None
        assert c.last_update_success
        assert fetch.await_count == 1
        assert await ha.async_add_executor_job(path.read_bytes) == corruption
        blocked = await finish_options(ha, entry, OPTIONS)
        assert blocked["type"] == "form"
        assert blocked["errors"] == {"base": "invalid_pellet_storage"}
        disabled = await finish_options(ha, entry, {**OPTIONS, ENABLED: False})
        assert disabled["type"] == "create_entry"
        await ha.async_block_till_done()
        assert await ha.async_add_executor_job(path.read_bytes) == corruption
        assert await async_unload_entry(ha, entry)
        await ha.async_add_executor_job(path.write_bytes, backup)
        # The current disabled option is written before enable, even if the
        # restored backup predates the disable and the entry is still unloaded.
        assert (await finish_options(ha, entry, OPTIONS))["type"] == "create_entry"
        assert await async_setup_entry(ha, entry)
        restored = ha.data[DOMAIN]["coordinators"][entry.entry_id]
        assert restored.pellet.state["kg"] == 1
        assert restored.pellet.state["previous"][0] == 30
        readings(restored, [31, 0, 0, 0, 0])
        await restored.pellet.async_update(restored)
        assert restored.pellet.state["kg"] == 1.5
        assert await async_unload_entry(ha, entry)


@pytest.mark.asyncio
async def test_options_wait_for_unload_and_keep_total(ha):  # noqa: F811
    entry = entry_for(ha, "unloading")
    entered, release = asyncio.Event(), asyncio.Event()

    async def delayed_unload(*_args):
        entered.set()
        await release.wait()
        return True

    with (
        patch.object(
            EdilkaminCoordinator,
            "update_device_information",
            AsyncMock(return_value=data_at(10)),
        ),
        patch.object(
            type(ha.config_entries), "async_forward_entry_setups", AsyncMock()
        ),
        patch.object(type(ha.config_entries), "async_unload_platforms", delayed_unload),
        patch.object(
            type(ha.config_entries), "async_reload", AsyncMock(return_value=True)
        ),
    ):
        assert await async_setup_entry(ha, entry)
        c = ha.data[DOMAIN]["coordinators"][entry.entry_id]
        readings(c, [12, 0, 0, 0, 0])
        await c.pellet.async_update(c)
        unload = asyncio.create_task(async_unload_entry(ha, entry))
        await asyncio.wait_for(entered.wait(), 2)
        disable = asyncio.create_task(
            finish_options(ha, entry, {**OPTIONS, ENABLED: False})
        )
        await asyncio.sleep(0)
        assert not disable.done()
        release.set()
        assert await asyncio.wait_for(unload, 2)
        assert (await asyncio.wait_for(disable, 2))["type"] == "create_entry"
        await ha.async_block_till_done()
        assert c.pellet.closed
        stored = await Store(ha, 1, "edilkamin_pellet_unloading").async_load()
        assert stored["kg"] == 1
        assert not stored["settings"][ENABLED]
        assert stored["previous"] == [None] * 5


@pytest.mark.asyncio
async def test_failed_setup_does_not_leave_live_estimator(ha):  # noqa: F811
    entry = entry_for(ha, "failed")
    with (
        patch.object(
            EdilkaminCoordinator,
            "update_device_information",
            AsyncMock(return_value=data_at(10)),
        ),
        patch.object(
            type(ha.config_entries),
            "async_forward_entry_setups",
            AsyncMock(side_effect=RuntimeError("platform failed")),
        ),
        pytest.raises(RuntimeError, match="platform failed"),
    ):
        await async_setup_entry(ha, entry)
    assert entry.entry_id not in ha.data[DOMAIN].get("coordinators", {})
    assert entry.entry_id not in ha.data[DOMAIN]
    result = await finish_options(ha, entry, {**OPTIONS, ENABLED: False})
    assert result["type"] == "create_entry"
    stored = await Store(ha, 1, "edilkamin_pellet_failed").async_load()
    assert not stored["settings"][ENABLED]
    assert stored["previous"] == [None] * 5


@pytest.mark.asyncio
async def test_live_corruption_is_not_overwritten(ha):  # noqa: F811
    entry = entry_for(ha, "live")
    with (
        patch.object(
            EdilkaminCoordinator,
            "update_device_information",
            AsyncMock(side_effect=[data_at(10), data_at(12)]),
        ),
        patch.object(
            type(ha.config_entries), "async_forward_entry_setups", AsyncMock()
        ),
        patch.object(
            type(ha.config_entries),
            "async_unload_platforms",
            AsyncMock(return_value=True),
        ),
        patch.object(
            type(ha.config_entries), "async_reload", AsyncMock(return_value=True)
        ),
    ):
        assert await async_setup_entry(ha, entry)
        c = ha.data[DOMAIN]["coordinators"][entry.entry_id]
        path = Path(c.pellet.store.path)
        corrupted = b"{broken while running"
        await ha.async_add_executor_job(path.write_bytes, corrupted)
        await c.async_refresh()
        assert c.last_update_success
        assert c.pellet.storage_invalid
        assert not EdilkaminPelletSensor(c).available
        assert not EdilkaminPelletIncompleteSensor(c).available
        assert await ha.async_add_executor_job(path.read_bytes) == corrupted
        result = await finish_options(ha, entry, {**OPTIONS, ENABLED: False})
        assert result["type"] == "create_entry"
        await ha.async_block_till_done()
        assert await ha.async_add_executor_job(path.read_bytes) == corrupted
        result = await finish_options(ha, entry, OPTIONS)
        assert result["errors"] == {"base": "invalid_pellet_storage"}
        assert await async_unload_entry(ha, entry)
