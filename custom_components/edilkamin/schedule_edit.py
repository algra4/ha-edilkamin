"""Read/modify/write weekly chrono data without changing operating modes."""

from __future__ import annotations

import asyncio
import contextlib
from copy import deepcopy
from datetime import date, datetime, time, timedelta
import json
import logging
from pathlib import Path
import re
from uuid import uuid4

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
import voluptuous as vol

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
MODES = {"off": 0, "economy": 1, "comfort": 2}
_LOGGER = logging.getLogger(__name__)


def valid_recovery(record):
    """Reject malformed durable data even when Python assertions are disabled."""
    try:
        deadline = dt_util.parse_datetime(record["restore_at"])
        return (
            isinstance(record["id"], str)
            and re.fullmatch(r"[0-9a-f]{32}", record["id"]) is not None
            and deadline is not None
            and deadline.tzinfo is not None
            and isinstance(record["original"], dict)
            and bool(record["original"])
            and type(record["applied"]) is int
            and record["applied"] in (0, 1, 2)
            and all(
                str(int(key)) == key
                and 0 <= int(key) < 336
                and type(value) is int
                and value in (0, 1, 2)
                and value != record["applied"]
                for key, value in record["original"].items()
            )
        )
    except (KeyError, TypeError, ValueError):
        return False


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


def validate_request(data):
    """Validate before authentication, backup or device access."""
    start = half_hour(data["start"])
    end = half_hour(data["end"], end=True)
    if end <= start:
        msg = "End must be after start. Split overnight ranges at midnight."
        raise vol.Invalid(msg)
    if data.get("auto_restore"):
        if len(set(data["days"])) != 1:
            msg = "Temporary windows require exactly one weekday."
            raise vol.Invalid(msg)
        if "date" in data:
            try:
                selected = date.fromisoformat(data["date"])
            except (ValueError, TypeError) as error:
                msg = "Date must be YYYY-MM-DD."
                raise vol.Invalid(msg) from error
            if (
                selected.isoformat() != data["date"]
                or DAYS[selected.weekday()] != data["days"][0]
            ):
                msg = "Date and weekday must match."
                raise vol.Invalid(msg)
    elif "date" in data:
        msg = "Date is allowed only with auto_restore."
        raise vol.Invalid(msg)
    return data


EDIT_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required("days"): vol.All([vol.In(DAYS)], vol.Length(min=1, max=7)),
            vol.Required("start"): str,
            vol.Required("end"): str,
            vol.Required("mode"): vol.In(MODES),
            vol.Optional("preview_only", default=False): bool,
            vol.Optional("auto_restore", default=False): bool,
            vol.Optional("date"): str,
        }
    ),
    validate_request,
)


def window_deadline(request, now):
    """Resolve one occurrence and persist its unambiguous UTC end, including DST."""
    offset = (DAYS.index(request["days"][0]) - now.weekday()) % 7
    chosen = (
        date.fromisoformat(request["date"])
        if "date" in request
        else now.date() + timedelta(days=offset)
    )
    end_slot = half_hour(request["end"], end=True)

    def boundary(day, slot):
        naive = datetime.combine(day, time()) + timedelta(minutes=slot * 30)
        local = naive.replace(tzinfo=now.tzinfo, fold=1)
        if dt_util.as_utc(local).astimezone(now.tzinfo).replace(tzinfo=None) != naive:
            msg = "This wall-clock time does not exist on the selected date due to DST."
            raise HomeAssistantError(msg)
        return local

    end = boundary(chosen, end_slot)
    if "date" not in request and dt_util.as_utc(end) <= dt_util.as_utc(now):
        chosen += timedelta(days=7)
        end = boundary(chosen, end_slot)
    if not 0 <= (chosen - now.date()).days <= 7 or dt_util.as_utc(
        end
    ) <= dt_util.as_utc(now):
        msg = "Temporary windows must end in the future within the next seven days."
        raise HomeAssistantError(msg)
    # A day seven days ahead is safe only after today's occurrence has ended.
    if (chosen - now.date()).days == 7 and dt_util.as_utc(
        boundary(now.date(), end_slot)
    ) > dt_util.as_utc(now):
        msg = "This weekly slot would already apply today; choose an earlier date."
        raise HomeAssistantError(msg)
    boundary(chosen, half_hour(request["start"]))
    return chosen.isoformat(), dt_util.as_utc(end).isoformat()


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

    def __init__(self, hass, api, coordinator, entry_id):
        self.hass, self.api, self.coordinator = hass, api, coordinator
        self.lock = asyncio.Lock()
        self.last_result = None
        self.windows = []
        self._store = Store(
            hass,
            1,
            "edilkamin_schedule_windows_" + entry_id,
        )
        self._loaded = False
        self._cancel_timer = None
        self._task = None
        self._stopped = False

    @property
    def pending_windows(self):
        return [
            {
                key: record.get(key)
                for key in (
                    "id",
                    "date",
                    "start",
                    "end",
                    "mode",
                    "restore_at",
                    "phase",
                    "last_error",
                )
            }
            for record in self.windows
        ]

    async def async_start(self):
        if self._loaded:
            return
        saved = await self._store.async_load()
        records = saved.get("windows", []) if isinstance(saved, dict) else []
        if saved is not None and (
            not isinstance(saved, dict)
            or "windows" not in saved
            or not isinstance(records, list)
        ):
            msg = "Invalid temporary window storage; check the saved recovery data."
            raise HomeAssistantError(msg)
        seen_ids, seen_slots = set(), set()
        for record in records:
            if not valid_recovery(record):
                fail("Saved recovery data is invalid; no schedule command sent.")
            slots = set(record["original"])
            if record["id"] in seen_ids or slots & seen_slots:
                fail("Overlapping saved recovery records; no schedule command sent.")
            seen_ids.add(record["id"])
            seen_slots.update(slots)
        self.windows = deepcopy(records)
        self._loaded = True
        self._arm(immediate=True)
        self._notify()

    async def _save(self):
        await self._store.async_save({"windows": deepcopy(self.windows)})

    def _arm(self, *, immediate=False):
        if self._cancel_timer:
            self._cancel_timer()
            self._cancel_timer = None
        if self.windows and not self._stopped:
            nearest = min(
                dt_util.parse_datetime(record["restore_at"]) for record in self.windows
            )
            delay = (nearest - dt_util.utcnow()).total_seconds()
            if delay <= 0:
                delay = 0 if immediate else 30
            self._cancel_timer = async_call_later(self.hass, delay, self._timer_fired)

    @callback
    def _timer_fired(self, _now):
        self._cancel_timer = None
        if not self._stopped and (self._task is None or self._task.done()):
            self._task = self.hass.async_create_task(self.restore_due())

    async def async_stop(self):
        self._stopped = True
        if self._cancel_timer:
            self._cancel_timer()
            self._cancel_timer = None
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def restore_due(self):
        """Read before each retry; restore only values still matching this window."""
        if self.lock.locked():
            self._arm()
            return
        async with self.lock:
            for record in list(self.windows):
                if dt_util.parse_datetime(record["restore_at"]) > dt_util.utcnow():
                    continue
                try:
                    before = await self._read()
                    self._validate_representations(before)
                    changed, preserved = await self._restore_record(record, before)
                    remaining = [
                        item for item in self.windows if item["id"] != record["id"]
                    ]
                    # Save completion before discarding the in-memory recovery record.
                    await self._store.async_save({"windows": deepcopy(remaining)})
                    self.windows = remaining
                    self.last_result = {
                        "status": "restored_with_external_changes"
                        if preserved
                        else "restored",
                        "window_id": record["id"],
                        "restored_slots": changed,
                        "preserved_external_slots": preserved,
                    }

                except Exception as error:
                    record["phase"] = "restore_pending"
                    record["last_error"] = type(error).__name__
                    self.last_result = {
                        "status": "restore_pending",
                        "window_id": record["id"],
                        "error": type(error).__name__,
                    }
                    _LOGGER.exception("Schedule restoration pending")
                    with contextlib.suppress(Exception):
                        # The pre-write recovery record remains on disk.
                        await self._save()
            self._arm()
            self._notify()
            await self._refresh()

    async def _restore_record(self, record, before):
        desired = deepcopy(before)
        preserved = []
        for key, original in record["original"].items():
            index = int(key)
            current = before["temperature_ranges"][index]
            if current == record["applied"]:
                desired["temperature_ranges"][index] = original
            elif current != original:
                preserved.append(index)
        changed = changed_slots(
            before["temperature_ranges"], desired["temperature_ranges"]
        )
        if changed:
            request = {
                "operation": "automatic_restore",
                "window_id": record["id"],
            }
            folder = await self.hass.async_add_executor_job(
                create_backup,
                self.hass.config.path(),
                self.coordinator.get_mac_address(),
                before,
                request,
                desired,
            )
            record["restore_backup"] = folder
            record["phase"] = "restoring"
            await self._save()
            if await self._read() != before:
                fail("The schedule changed during restoration preparation.")
            actual = await self._send_verified(before, desired)
            await self.hass.async_add_executor_job(
                save_result,
                folder,
                {
                    "status": "restored",
                    "window_id": record["id"],
                    "preserved_external_slots": preserved,
                },
                actual,
            )
        return changed, preserved

    def _validate_representations(self, before):
        # An accepted write may leave power_ranges unchanged. Allow only the
        # differences explained by our durable, nonoverlapping recovery records.
        owned = {
            int(key): (item["applied"], original)
            for item in self.windows
            for key, original in item["original"].items()
        }
        for index, (temperature, power) in enumerate(
            zip(before["temperature_ranges"], before["power_ranges"], strict=True)
        ):
            if temperature != power and owned.get(index) != (temperature, power):
                fail("Unexplained chrono representations; no schedule command sent.")

    def _notify(self):
        self.coordinator.schedule_edit_status = {
            "temporary_windows": self.pending_windows,
            "last_schedule_edit": deepcopy(self.last_result),
        }
        self.coordinator.async_update_listeners()

    async def _refresh(self):
        # Readback already verified the command. A refresh failure does not undo it.
        with contextlib.suppress(Exception):
            await self.coordinator.async_request_refresh()

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

    async def _prepare_window(self, request, result, before, modified, folder):
        window = None
        if request["auto_restore"]:
            if dt_util.parse_datetime(result["restore_at"]) <= dt_util.utcnow():
                fail("The window has ended; no schedule command sent.")
            window = {
                "id": uuid4().hex,
                "date": result["date"],
                "start": request["start"],
                "end": request["end"],
                "mode": request["mode"],
                "restore_at": result["restore_at"],
                "phase": "armed",
                "backup": folder,
                "original": {
                    str(index): before["temperature_ranges"][index]
                    for index in modified
                },
                "applied": MODES[request["mode"]],
            }
            self.windows.append(window)
            try:
                await self._save()
            except Exception:
                self.windows.remove(window)
                raise
            result["window_id"] = window["id"]
            self._arm()
        return window

    def _describe_edit(self, request, before, desired):
        selected = {
            DAYS.index(day) * 48 + slot
            for day in set(request["days"])
            for slot in range(
                half_hour(request["start"]), half_hour(request["end"], end=True)
            )
        }
        if any(set(map(int, item["original"])) & selected for item in self.windows):
            fail("This range already belongs to a temporary window; await restoration.")
        modified = changed_slots(
            before["temperature_ranges"], desired["temperature_ranges"]
        )
        result = {
            "status": "preview" if request["preview_only"] else "unchanged",
            "recurrence": "once" if request["auto_restore"] else "weekly",
            "days": list(dict.fromkeys(request["days"])),
            "start": request["start"],
            "end": request["end"],
            "mode": request["mode"],
            "changed_slots": modified,
            "chrono_active": bool(before["is_active"]),
            "write_attempts": 0,
        }
        if request["auto_restore"]:
            result["date"], result["restore_at"] = window_deadline(
                request, dt_util.now()
            )
        return result, modified

    async def set_schedule(self, data):
        # ServiceCall.data is read-only; validation may add default values.
        request = EDIT_SCHEMA(dict(data))
        async with self.lock:
            await self.async_start()
            try:
                before = await self._read()
                self._validate_representations(before)
                desired = edit(before, request)
                result, modified = self._describe_edit(request, before, desired)
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
                window = await self._prepare_window(
                    request, result, before, modified, folder
                )
                actual = None
                try:
                    actual = await self._send_verified(before, desired)
                    result.update(
                        status="verified",
                        power_ranges_changed_slots=changed_slots(
                            before["power_ranges"], actual["power_ranges"]
                        ),
                    )
                    if window:
                        window["phase"] = "active"
                        await self._save()
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
                await self._refresh()
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
            finally:
                self._notify()
