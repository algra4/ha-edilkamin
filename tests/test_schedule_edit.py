"""Schedule edits use a simulated cloud and isolated backup directory only."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.exceptions import HomeAssistantError
import pytest
import voluptuous as vol

from custom_components.edilkamin.schedule_edit import ScheduleWriter


class TestSchedule(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.info = {
            "nvm": {
                "user_parameters": {"is_auto": True},
                "chrono": {
                    "temperature_ranges": [0] * 336,
                    "power_ranges": [0] * 336,
                    "economy_temperature": 20,
                    "comfort_temperature": 22,
                    "is_active": True,
                },
            }
        }
        self.api = Mock()
        self.api.get_info = AsyncMock(side_effect=lambda: deepcopy(self.info))

        async def command(payload):
            assert payload["name"] == "chrono_temperature_ranges"
            self.info["nvm"]["chrono"]["temperature_ranges"] = list(payload["value"])
            self.info["nvm"]["chrono"]["power_ranges"] = list(payload["value"])

        self.api.execute_command = AsyncMock(side_effect=command)
        self.hass = Mock()
        self.hass.data = {}
        self.hass.config.path.return_value = self.temp.name

        async def executor(function, *args):
            return function(*args)

        self.hass.async_add_executor_job = AsyncMock(side_effect=executor)
        self.coordinator = Mock(async_request_refresh=AsyncMock())
        self.coordinator.get_mac_address.return_value = "00:11:22:33:44:55"
        self.override = False
        self.writer = ScheduleWriter(self.hass, self.api, self.coordinator)
        self.request = {
            "days": ["tuesday"],
            "start": "23:30",
            "end": "24:00",
            "mode": "comfort",
        }

    async def test_only_requested_tuesday_slot_and_backup_before_command(self):
        original = deepcopy(self.info)
        original_command = self.api.execute_command.side_effect

        async def with_backup(payload):
            files = list(Path(self.temp.name).glob("edilkamin-backups/*/before.json"))
            assert len(files) == 1
            assert (
                json.loads(files[0].read_text())["chrono"] == original["nvm"]["chrono"]
            )
            assert (
                json.loads(files[0].with_name("result.json").read_text())["result"][
                    "status"
                ]
                == "pending"
            )
            await original_command(payload)

        self.api.execute_command.side_effect = with_backup
        result = await self.writer.set_schedule(self.request)
        assert result["status"] == "verified"
        assert result["changed_slots"] == result["power_ranges_changed_slots"] == [95]
        assert self.api.execute_command.await_count == 1
        original["nvm"]["chrono"]["temperature_ranges"][95] = 2
        original["nvm"]["chrono"]["power_ranges"][95] = 2
        assert self.info == original

    async def test_multi_day_half_hours_and_sunday_day_boundary(self):
        result = await self.writer.set_schedule(
            {
                "days": ["monday", "sunday", "sunday"],
                "start": "00:30",
                "end": "01:30",
                "mode": "economy",
            }
        )
        assert result["changed_slots"] == [1, 2, 289, 290]

    async def test_off_preserves_remaining_modes(self):
        for field in ("temperature_ranges", "power_ranges"):
            self.info["nvm"]["chrono"][field] = [2] * 336
        result = await self.writer.set_schedule({**self.request, "mode": "off"})
        assert result["changed_slots"] == [95]
        assert self.info["nvm"]["chrono"]["temperature_ranges"][94:97] == [2, 0, 2]

    async def test_preview_sends_no_write_and_creates_no_backup(self):
        result = await self.writer.set_schedule({**self.request, "preview_only": True})
        assert result["status"] == "preview"
        assert result["changed_slots"] == [95]
        self.api.execute_command.assert_not_called()
        assert not list(Path(self.temp.name).iterdir())

    async def test_noop_sends_no_command(self):
        result = await self.writer.set_schedule({**self.request, "mode": "off"})
        assert result["status"] == "unchanged"
        self.api.execute_command.assert_not_called()

    async def test_invalid_requests_do_not_access_cloud(self):
        invalid = [
            {"start": "23:15"},
            {"start": "24:00"},
            {"end": "24:30"},
            {"end": "00:30"},
            {"end": "23:30"},
            {"start": "6:00"},
            {"days": []},
            {"days": ["Tuesday"]},
            {"days": "tuesday"},
            {"mode": "power_2"},
            {"mode": 2},
            {"preview_only": "false"},
        ]
        for fields in invalid:
            with self.subTest(fields=fields), pytest.raises(vol.Invalid):
                await self.writer.set_schedule({**self.request, **fields})
        self.api.get_info.assert_not_called()
        self.api.execute_command.assert_not_called()

    async def test_manual_mode_refused(self):
        self.info["nvm"]["user_parameters"]["is_auto"] = False
        with pytest.raises(HomeAssistantError):
            await self.writer.set_schedule(self.request)
        self.api.execute_command.assert_not_called()

    async def test_divergent_representations_refused(self):
        self.info["nvm"]["chrono"]["power_ranges"][5] = 5
        with pytest.raises(HomeAssistantError):
            await self.writer.set_schedule(self.request)
        self.api.execute_command.assert_not_called()

    async def test_malformed_or_missing_week_data_refused(self):
        original = deepcopy(self.info)
        for malformed in ([0] * 48, [0] * 335 + [True], [0] * 335 + [3], None):
            self.info = deepcopy(original)
            self.info["nvm"]["chrono"]["temperature_ranges"] = malformed
            with (
                self.subTest(value=repr(malformed)[-20:]),
                pytest.raises(HomeAssistantError),
            ):
                await self.writer.set_schedule(self.request)
        self.api.execute_command.assert_not_called()

    async def test_disabled_chrono_remains_disabled(self):
        self.info["nvm"]["chrono"]["is_active"] = False
        result = await self.writer.set_schedule(self.request)
        assert result["status"] == "verified"
        assert not result["chrono_active"]
        assert self.api.execute_command.await_count == 1

    async def test_concurrent_app_edit_aborts_without_write(self):
        original = deepcopy(self.info)
        self.info["nvm"]["chrono"]["temperature_ranges"][1] = 1
        self.api.get_info.side_effect = [original, deepcopy(self.info)]
        with pytest.raises(HomeAssistantError, match="schedule changed"):
            await self.writer.set_schedule(self.request)
        self.api.execute_command.assert_not_called()
        assert self.writer.last_result["status"] == "conflict"

    async def test_backup_failure_sends_no_command(self):
        self.hass.async_add_executor_job.side_effect = OSError("disk full")
        with pytest.raises(HomeAssistantError):
            await self.writer.set_schedule(self.request)
        self.api.execute_command.assert_not_called()

    async def test_cloud_read_failure_sends_no_command(self):
        self.api.get_info.side_effect = OSError("offline")
        with pytest.raises(HomeAssistantError):
            await self.writer.set_schedule(self.request)
        self.api.execute_command.assert_not_called()

    async def test_ambiguous_write_is_not_retried(self):
        self.api.execute_command.side_effect = TimeoutError()
        with pytest.raises(HomeAssistantError, match="not retried"):
            await self.writer.set_schedule(self.request)
        assert self.api.execute_command.await_count == 1
        assert self.writer.last_result["status"] == "unconfirmed"

    async def test_unrelated_readback_change_is_not_success(self):
        command = self.api.execute_command.side_effect

        async def corrupt(payload):
            await command(payload)
            self.info["nvm"]["chrono"]["power_ranges"][1] = 3

        self.api.execute_command.side_effect = corrupt
        with (
            patch(
                "custom_components.edilkamin.schedule_edit.asyncio.sleep",
                new=AsyncMock(),
            ),
            pytest.raises(HomeAssistantError),
        ):
            await self.writer.set_schedule(self.request)
        assert self.api.execute_command.await_count == 1
        assert self.writer.last_result["status"] == "unconfirmed"

    async def test_power_representation_may_remain_unchanged(self):
        async def command(payload):
            self.info["nvm"]["chrono"]["temperature_ranges"] = list(payload["value"])

        self.api.execute_command.side_effect = command
        result = await self.writer.set_schedule(self.request)
        assert result["status"] == "verified"
        assert result["power_ranges_changed_slots"] == []

    async def test_delayed_readback_is_verified_without_second_write(self):
        original = deepcopy(self.info)
        self.api.get_info.side_effect = [
            original,
            original,
            original,
            {
                "nvm": {
                    "user_parameters": {"is_auto": True},
                    "chrono": {
                        **original["nvm"]["chrono"],
                        "temperature_ranges": [0] * 95 + [2] + [0] * 240,
                    },
                }
            },
        ]
        with patch(
            "custom_components.edilkamin.schedule_edit.asyncio.sleep", new=AsyncMock()
        ):
            result = await self.writer.set_schedule(self.request)
        assert result["status"] == "verified"
        assert self.api.execute_command.await_count == 1


if __name__ == "__main__":
    unittest.main()
