"""Simulated cloud plus real HA storage for restart-safe one-off windows."""

import asyncio
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
import voluptuous as vol

from custom_components.edilkamin.schedule_edit import (
    EDIT_SCHEMA,
    ScheduleWriter,
    window_deadline,
)
from tests import test_schedule_edit as baseline


class TestAutomaticReturn(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = baseline.TestSchedule.asyncSetUp

    async def once(self, **fields):
        request = {**self.request, "auto_restore": True, "date": "2026-11-17", **fields}
        now = datetime(2026, 11, 17, 20, tzinfo=ZoneInfo("Europe/Berlin"))
        with (
            patch(
                "custom_components.edilkamin.schedule_edit.dt_util.now",
                return_value=now,
            ),
            patch(
                "custom_components.edilkamin.schedule_edit.dt_util.utcnow",
                return_value=now.astimezone(ZoneInfo("UTC")),
            ),
        ):
            return await self.writer.set_schedule(request)

    async def expire(self, writer=None):
        now = datetime(2026, 11, 17, 23, tzinfo=ZoneInfo("UTC"))
        with patch(
            "custom_components.edilkamin.schedule_edit.dt_util.utcnow",
            return_value=now,
        ):
            await (writer or self.writer).restore_due()

    async def test_once_persists_original_before_first_write(self):
        command = self.api.execute_command.side_effect

        async def assert_durable(payload):
            saved = self.writer._store.async_save.await_args.args[0]["windows"][0]
            assert saved["original"] == {"95": 0}
            assert saved["applied"] == 2
            assert saved["phase"] == "armed"
            assert saved["restore_at"] == "2026-11-17T23:00:00+00:00"
            await command(payload)

        self.api.execute_command.side_effect = assert_durable
        result = await self.once()
        assert result["recurrence"] == "once"
        assert result["window_id"]
        assert self.writer.pending_windows[0]["phase"] == "active"
        self.api.execute_command.side_effect = command
        await self.expire()
        assert self.info["nvm"]["chrono"]["temperature_ranges"][95] == 0
        assert self.info["nvm"]["chrono"]["power_ranges"][95] == 0
        assert not self.writer.windows
        assert self.api.execute_command.await_count == 2

    async def test_restore_never_runs_before_deadline(self):
        await self.once()
        with patch(
            "custom_components.edilkamin.schedule_edit.dt_util.utcnow",
            return_value=datetime(2026, 11, 17, 22, 59, tzinfo=ZoneInfo("UTC")),
        ):
            await self.writer.restore_due()
        assert len(self.writer.windows) == 1
        assert self.api.execute_command.await_count == 1

    async def test_nonmirrored_power_is_restored(self):
        async def temperature_only(payload):
            self.info["nvm"]["chrono"]["temperature_ranges"] = list(payload["value"])

        self.api.execute_command.side_effect = temperature_only
        await self.once()
        assert self.info["nvm"]["chrono"]["power_ranges"][95] == 0
        await self.expire()
        assert not self.writer.windows
        assert self.info["nvm"]["chrono"]["temperature_ranges"][95] == 0
        assert self.api.execute_command.await_count == 2

    async def test_manual_mode_defers_restore_without_command(self):
        await self.once()
        self.info["nvm"]["user_parameters"]["is_auto"] = False
        await self.expire()
        assert self.writer.windows[0]["phase"] == "restore_pending"
        assert self.api.execute_command.await_count == 1
        self.info["nvm"]["user_parameters"]["is_auto"] = True
        await self.expire()
        assert not self.writer.windows

    async def test_unrelated_divergence_is_not_overwritten(self):
        await self.once()
        self.info["nvm"]["chrono"]["power_ranges"][1] = 5
        await self.expire()
        assert self.writer.windows[0]["phase"] == "restore_pending"
        assert self.api.execute_command.await_count == 1

    async def test_restore_waits_for_writer_lock(self):
        await self.once()
        async with self.writer.lock:
            await self.expire()
        assert self.api.execute_command.await_count == 1
        await self.expire()
        assert not self.writer.windows

    async def test_refresh_failure_does_not_undo_verified_recovery(self):
        self.coordinator.async_request_refresh.side_effect = OSError("offline")
        assert (await self.once())["status"] == "verified"
        await self.expire()
        assert not self.writer.windows
        assert self.writer.last_result["status"] == "restored"

    async def test_restore_concurrent_edit_defers_then_preserves_it(self):
        await self.once()
        before = deepcopy(self.info)
        self.info["nvm"]["chrono"]["temperature_ranges"][10] = 1
        self.info["nvm"]["chrono"]["power_ranges"][10] = 1
        self.api.get_info.side_effect = [before, deepcopy(self.info)]
        await self.expire()
        assert self.api.execute_command.await_count == 1
        self.api.get_info.side_effect = lambda: deepcopy(self.info)
        await self.expire()
        assert not self.writer.windows
        assert self.info["nvm"]["chrono"]["temperature_ranges"][10] == 1

    async def test_completed_storage_failure_rechecks_before_retry(self):
        await self.once()
        self.writer._store.async_save.side_effect = [None, OSError("disk full"), None]
        await self.expire()
        assert len(self.writer.windows) == 1
        assert self.api.execute_command.await_count == 2
        self.writer._store.async_save.side_effect = None
        await self.expire()
        assert not self.writer.windows
        assert self.api.execute_command.await_count == 2

    async def test_two_entries_keep_independent_durable_recovery(self):
        hass = HomeAssistant(self.temp.name)
        writers = [
            ScheduleWriter(hass, self.api, self.coordinator, entry)
            for entry in ("first", "second")
        ]
        for writer in writers:
            writer._arm = Mock()
        now = datetime(2026, 11, 17, 20, tzinfo=ZoneInfo("Europe/Berlin"))
        with (
            patch(
                "custom_components.edilkamin.schedule_edit.dt_util.now",
                return_value=now,
            ),
            patch(
                "custom_components.edilkamin.schedule_edit.dt_util.utcnow",
                return_value=now.astimezone(ZoneInfo("UTC")),
            ),
        ):
            for writer, start in zip(writers, ("22:00", "23:30"), strict=True):
                await writer.set_schedule(
                    {
                        **self.request,
                        "start": start,
                        "end": "22:30" if start == "22:00" else "24:00",
                        "auto_restore": True,
                        "date": "2026-11-17",
                    }
                )
        assert writers[0].windows[0]["original"] == {"92": 0}
        assert writers[1].windows[0]["original"] == {"95": 0}
        for writer in writers:
            await writer.async_stop()
        for entry, slot in (("first", "92"), ("second", "95")):
            restarted = ScheduleWriter(
                HomeAssistant(self.temp.name), self.api, self.coordinator, entry
            )
            restarted._arm = Mock()
            await restarted.async_start()
            assert restarted.windows[0]["original"] == {slot: 0}
            await restarted.async_stop()

    async def test_preview_and_noop_do_not_claim_original_values(self):
        result = await self.once(preview_only=True)
        assert result["restore_at"] == "2026-11-17T23:00:00+00:00"
        result = await self.once(mode="off")
        assert result["status"] == "unchanged"
        assert not self.writer.windows
        self.writer._store.async_save.assert_not_called()
        self.api.execute_command.assert_not_called()

    async def test_overlap_refuses_temporary_and_permanent_edits(self):
        await self.once()
        with pytest.raises(HomeAssistantError, match="already"):
            await self.once(mode="economy")
        with pytest.raises(HomeAssistantError, match="already"):
            await self.writer.set_schedule({**self.request, "mode": "off"})
        assert self.api.execute_command.await_count == 1

    async def test_nonoverlapping_windows_restore_independently(self):
        first = await self.once(start="22:00", end="22:30")
        second = await self.once()
        assert first["window_id"] != second["window_id"]
        with patch(
            "custom_components.edilkamin.schedule_edit.dt_util.utcnow",
            return_value=datetime(2026, 11, 17, 21, 30, tzinfo=ZoneInfo("UTC")),
        ):
            await self.writer.restore_due()
        assert len(self.writer.windows) == 1
        assert self.info["nvm"]["chrono"]["temperature_ranges"][92:96] == [0, 0, 0, 2]
        await self.expire()
        assert not self.writer.windows

    async def test_external_edits_and_new_temperature_are_preserved(self):
        await self.once(start="23:00")
        for key in ("temperature_ranges", "power_ranges"):
            self.info["nvm"]["chrono"][key][94] = 1
            self.info["nvm"]["chrono"][key][10] = 1
        self.info["nvm"]["chrono"]["economy_temperature"] = 19
        await self.expire()
        assert self.info["nvm"]["chrono"]["temperature_ranges"][94:96] == [1, 0]
        assert self.info["nvm"]["chrono"]["temperature_ranges"][10] == 1
        assert self.info["nvm"]["chrono"]["economy_temperature"] == 19
        assert self.writer.last_result["preserved_external_slots"] == [94]
        assert not self.writer.windows

    async def test_cloud_failure_retains_recovery_then_retries(self):
        await self.once()
        self.api.get_info.side_effect = OSError("offline")
        await self.expire()
        assert self.writer.windows[0]["phase"] == "restore_pending"
        assert self.api.execute_command.await_count == 1
        self.api.get_info.side_effect = lambda: deepcopy(self.info)
        await self.expire()
        assert not self.writer.windows
        assert self.api.execute_command.await_count == 2

    async def test_ambiguous_restore_reads_before_any_retry(self):
        await self.once()
        command = self.api.execute_command.side_effect

        async def applied_but_timeout(payload):
            await command(payload)
            raise TimeoutError

        self.api.execute_command.side_effect = applied_but_timeout
        await self.expire()
        assert self.writer.windows
        assert self.api.execute_command.await_count == 2
        await self.expire()
        assert not self.writer.windows
        assert self.api.execute_command.await_count == 2

    async def test_unconfirmed_initial_write_keeps_rollback(self):
        command = self.api.execute_command.side_effect

        async def applied_but_timeout(payload):
            await command(payload)
            raise TimeoutError

        self.api.execute_command.side_effect = applied_but_timeout
        with pytest.raises(HomeAssistantError):
            await self.once()
        assert self.writer.windows[0]["phase"] == "armed"
        self.api.execute_command.side_effect = command
        await self.expire()
        assert not self.writer.windows

    async def test_recovery_save_failure_prevents_initial_write(self):
        self.writer._store.async_save.side_effect = OSError("disk full")
        with pytest.raises(HomeAssistantError):
            await self.once()
        assert not self.writer.windows
        self.api.execute_command.assert_not_called()

    async def test_durable_recovery_survives_real_ha_storage_restart(self):
        writer = ScheduleWriter(
            HomeAssistant(self.temp.name),
            self.api,
            self.coordinator,
            "test-entry",
        )
        writer._arm = Mock()
        now = datetime(2026, 11, 17, 20, tzinfo=ZoneInfo("Europe/Berlin"))
        with (
            patch(
                "custom_components.edilkamin.schedule_edit.dt_util.now",
                return_value=now,
            ),
            patch(
                "custom_components.edilkamin.schedule_edit.dt_util.utcnow",
                return_value=now.astimezone(ZoneInfo("UTC")),
            ),
        ):
            await writer.set_schedule(
                {**self.request, "auto_restore": True, "date": "2026-11-17"}
            )
        files = list(Path(self.temp.name).glob(".storage/edilkamin_schedule_windows_*"))
        assert len(files) == 1
        assert json.loads(files[0].read_text())["data"]["windows"][0]["original"] == {
            "95": 0
        }
        await writer.async_stop()
        restarted = ScheduleWriter(
            HomeAssistant(self.temp.name),
            self.api,
            self.coordinator,
            "test-entry",
        )
        restarted._arm = Mock()
        await restarted.async_start()
        assert len(restarted.windows) == 1
        await self.expire(restarted)
        assert not restarted.windows
        assert json.loads(files[0].read_text())["data"]["windows"] == []
        await restarted.async_stop()

    async def test_exact_deadline_timer_and_unload_cancellation(self):
        await self.once()
        with (
            patch(
                "custom_components.edilkamin.schedule_edit.dt_util.utcnow",
                return_value=datetime(2026, 11, 17, 22, tzinfo=ZoneInfo("UTC")),
            ),
            patch(
                "custom_components.edilkamin.schedule_edit.async_call_later"
            ) as later,
        ):
            ScheduleWriter._arm(self.writer)
            assert later.call_args.args[1] == 3600
            cancel = later.return_value
        await self.writer.async_stop()
        cancel.assert_called_once()

    async def test_real_ha_timer_executes_restoration_on_event_loop(self):
        await self.once()
        self.writer.hass = HomeAssistant(self.temp.name)
        self.writer._arm = ScheduleWriter._arm.__get__(self.writer)
        with patch(
            "custom_components.edilkamin.schedule_edit.dt_util.utcnow",
            return_value=datetime(2026, 11, 17, 23, tzinfo=ZoneInfo("UTC")),
        ):
            self.writer._arm(immediate=True)
            for _ in range(100):
                if not self.writer.windows:
                    break
                await asyncio.sleep(0.01)
            assert not self.writer.windows
        await self.writer.async_stop()

    async def test_corrupt_recovery_is_not_silently_discarded(self):
        self.writer._store.async_load.return_value = {"wrong_key": []}
        with pytest.raises(HomeAssistantError):
            await self.writer.async_start()
        self.writer._store.async_load.return_value = {
            "windows": [{"restore_at": "2026-11-17T23:00:00+00:00"}]
        }
        with pytest.raises(HomeAssistantError):
            await self.writer.async_start()
        self.api.execute_command.assert_not_called()

    async def test_invalid_once_fields_dates_and_horizon(self):
        for fields in [
            {"days": ["monday", "tuesday"]},
            {"date": "2026-11-18"},
            {"date": "2026-02-30"},
        ]:
            with self.subTest(fields=fields), pytest.raises(vol.Invalid):
                await self.once(**fields)
        with pytest.raises(vol.Invalid):
            await self.writer.set_schedule({**self.request, "date": "2026-11-17"})
        for day in ["2026-11-10", "2026-12-01", "2026-11-24"]:
            with self.subTest(day=day), pytest.raises(HomeAssistantError):
                await self.once(date=day)
        self.api.execute_command.assert_not_called()

    async def test_next_occurrence_midnight_and_dst(self):
        request = EDIT_SCHEMA({**self.request, "auto_restore": True})
        now = datetime(2026, 11, 18, 0, 1, tzinfo=ZoneInfo("Europe/Berlin"))
        assert window_deadline(request, now) == (
            "2026-11-24",
            "2026-11-24T23:00:00+00:00",
        )
        dst = EDIT_SCHEMA(
            {
                "days": ["sunday"],
                "start": "01:00",
                "end": "02:30",
                "mode": "comfort",
                "auto_restore": True,
                "date": "2026-10-25",
            }
        )
        assert (
            window_deadline(
                dst, datetime(2026, 10, 24, tzinfo=ZoneInfo("Europe/Berlin"))
            )[1]
            == "2026-10-25T01:30:00+00:00"
        )
        dst["date"] = "2026-03-29"
        with pytest.raises(HomeAssistantError):
            window_deadline(
                dst, datetime(2026, 3, 28, tzinfo=ZoneInfo("Europe/Berlin"))
            )


if __name__ == "__main__":
    unittest.main()
