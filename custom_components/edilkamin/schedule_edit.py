"""Read/modify/write weekly chrono data without changing operating modes."""

from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from pathlib import Path
import re
from uuid import uuid4

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
import voluptuous as vol

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
MODES = {"off": 0, "economy": 1, "comfort": 2}


def half_hour(value: str, *, end: bool = False) -> int:
    """Parse local half-hour boundaries; 24:00 is an end boundary only."""
    if end and value == "24:00":
        return 48
    if not isinstance(value, str) or not re.fullmatch(
        r"(?:[01]\d|2[0-3]):(?:00|30)", value
    ):
        message = "Use HH:00 or HH:30; 24:00 is allowed only as an end."
        raise vol.Invalid(message)
    hour, minute = map(int, value.split(":"))
    return hour * 2 + minute // 30


def validate_range(data):
    if half_hour(data["end"], end=True) <= half_hour(data["start"]):
        message = "End must be after start. Split overnight ranges at midnight."
        raise vol.Invalid(message)
    return data


EDIT_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required("days"): vol.All([vol.In(DAYS)], vol.Length(min=1, max=7)),
            vol.Required("start"): str,
            vol.Required("end"): str,
            vol.Required("mode"): vol.In(MODES),
            vol.Optional("preview_only", default=False): bool,
        }
    ),
    validate_range,
)


def fail(message):
    raise HomeAssistantError(message)


def snapshot(info):
    """Validate full weekly data, not an empty fallback for missing values."""
    nvm = info.get("nvm") if isinstance(info, dict) else None
    if not isinstance(nvm, dict) or not isinstance(nvm.get("user_parameters"), dict):
        fail("The cloud did not return a complete weekly schedule.")
    auto = nvm["user_parameters"].get("is_auto")
    if type(auto) not in (bool, int) or auto != 1:
        fail("Schedule editing is currently supported only in automatic mode.")
    chrono = nvm.get("chrono")
    if not isinstance(chrono, dict):
        fail("The cloud did not return chrono data.")
    active = chrono.get("is_active")
    if type(active) not in (bool, int) or active not in (0, 1):
        fail("The cloud did not return a valid chrono enablement flag.")
    for key, maximum in (("temperature_ranges", 2), ("power_ranges", 5)):
        values = chrono.get(key)
        if (
            not isinstance(values, list)
            or len(values) != 336
            or any(
                type(value) is not int or not 0 <= value <= maximum for value in values
            )
        ):
            fail(f"Invalid weekly schedule: {key}.")
    return deepcopy(chrono)


def edit(chrono, request):
    result = deepcopy(chrono)
    start, end = half_hour(request["start"]), half_hour(request["end"], end=True)
    for day in set(request["days"]):
        offset = DAYS.index(day) * 48
        result["temperature_ranges"][offset + start : offset + end] = [
            MODES[request["mode"]]
        ] * (end - start)
    return result


def changed_slots(before, after):
    return [
        index
        for index, (old, new) in enumerate(zip(before, after, strict=True))
        if old != new
    ]


def verified(before, desired, actual):
    """The cloud may mirror a shared schedule under both array names."""
    if actual["temperature_ranges"] != desired["temperature_ranges"]:
        return False
    if actual["power_ranges"] not in (
        before["power_ranges"],
        desired["temperature_ranges"],
    ):
        return False
    excluded = {"temperature_ranges", "power_ranges"}
    return {key: value for key, value in before.items() if key not in excluded} == {
        key: value for key, value in actual.items() if key not in excluded
    }


def create_backup(root, mac, before, request, desired):
    """Persist the previous plan and proposed request before a device command."""
    folder = (
        Path(root)
        / "edilkamin-backups"
        / (
            "schedule-"
            + dt_util.utcnow().strftime("%Y%m%dT%H%M%SZ")
            + "-"
            + uuid4().hex
        )
    )
    folder.mkdir(parents=True, exist_ok=False)
    for name, data in {
        "before.json": {"mac_address": mac, "chrono": before},
        "request.json": request,
        "proposed-command.json": {
            "name": "chrono_temperature_ranges",
            "value": desired["temperature_ranges"],
        },
    }.items():
        with (folder / name).open("x", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
    return str(folder)


def save_result(folder, result, actual=None):
    target = Path(folder) / "result.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"result": result, "readback": actual}, indent=2), encoding="utf-8"
    )
    temporary.replace(target)


class ScheduleWriter:
    """Serialize edits per config entry, with fresh cloud reads and backups."""

    def __init__(self, hass, api, coordinator):
        self.hass, self.api, self.coordinator = hass, api, coordinator
        self.lock = asyncio.Lock()
        self.last_result = None

    async def _read(self):
        async with asyncio.timeout(20):
            return snapshot(await self.api.get_info())

    async def _send_verified(self, before, desired):
        # No automatic write retry: a timeout does not prove a command was rejected.
        async with asyncio.timeout(20):
            await self.api.execute_command(
                {
                    "name": "chrono_temperature_ranges",
                    "value": desired["temperature_ranges"],
                }
            )
        async with asyncio.timeout(45):
            for attempt in range(8):
                if attempt:
                    await asyncio.sleep(3)
                actual = await self._read()
                if verified(before, desired, actual):
                    return actual
        message = "The cloud readback does not match the complete expected schedule."
        raise HomeAssistantError(message)

    async def set_schedule(self, data):
        # ServiceCall.data is read-only; validation may add default values.
        request = EDIT_SCHEMA(dict(data))
        async with self.lock:
            try:
                before = await self._read()
                if before["temperature_ranges"] != before["power_ranges"]:
                    fail(
                        "Editing differing chrono representations has not been "
                        "validated; no command was sent."
                    )
                desired = edit(before, request)
                modified = changed_slots(
                    before["temperature_ranges"], desired["temperature_ranges"]
                )
                result = {
                    "status": "preview" if request["preview_only"] else "unchanged",
                    "recurrence": "weekly",
                    "days": list(dict.fromkeys(request["days"])),
                    "start": request["start"],
                    "end": request["end"],
                    "mode": request["mode"],
                    "changed_slots": modified,
                    "chrono_active": bool(before["is_active"]),
                    "write_attempts": 0,
                }
                if request["preview_only"] or not modified:
                    self.last_result = result
                    return result
                folder = await self.hass.async_add_executor_job(
                    create_backup,
                    self.hass.config.path(),
                    self.coordinator.get_mac_address(),
                    before,
                    request,
                    desired,
                )
                result["backup"] = folder
                if await self._read() != before:
                    result["status"] = "conflict"
                    self.last_result = result
                    await self.hass.async_add_executor_job(save_result, folder, result)
                    fail(
                        "The schedule changed while preparing this edit. "
                        "Read it again; no command was sent."
                    )
                result.update(status="pending", write_attempts=1)
                await self.hass.async_add_executor_job(save_result, folder, result)
                actual = None
                try:
                    actual = await self._send_verified(before, desired)
                    result.update(
                        status="verified",
                        power_ranges_changed_slots=changed_slots(
                            before["power_ranges"], actual["power_ranges"]
                        ),
                    )
                except Exception as error:
                    result.update(status="unconfirmed", error=type(error).__name__)
                    self.last_result = result
                    await self.hass.async_add_executor_job(
                        save_result, folder, result, actual
                    )
                    message = (
                        "Schedule write not confirmed; it was not retried. "
                        f"Check The Mind. Backup: {folder}."
                    )
                    raise HomeAssistantError(message) from error
                self.last_result = result
                await self.hass.async_add_executor_job(
                    save_result, folder, result, actual
                )
                await self.coordinator.async_request_refresh()
            except HomeAssistantError:
                raise
            except Exception as error:
                message = (
                    "Schedule editing failed; check cloud connectivity "
                    "and backup storage."
                )
                raise HomeAssistantError(message) from error
            else:
                return result
