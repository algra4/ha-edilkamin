"""Durable, per-entry pellet estimate; no polling or device commands."""

import asyncio
from copy import deepcopy
import json
import logging
import math
from pathlib import Path

from homeassistant.helpers.storage import Store
import voluptuous as vol

from .const import DOMAIN

ENABLED = "pellet_estimate_enabled"
COEFFICIENTS = tuple(f"pellet_p{power}_kg_h" for power in range(1, 6))
_LOGGER = logging.getLogger(__name__)


class InvalidPelletStorageError(ValueError):
    """The existing accumulator cannot safely be read or overwritten."""

    def __init__(self):
        super().__init__("Invalid pellet estimate storage; restore backup")


def entry_lock(hass, entry_id):
    """Serialize setup, unloaded option flows and unload per config entry."""
    locks = hass.data.setdefault(DOMAIN, {}).setdefault("pellet_locks", {})
    return locks.setdefault(entry_id, asyncio.Lock())


def coefficient(value):
    """Accept a positive finite rate, never bool/zero; blank means unknown."""
    message = "Enter a positive finite kg/h value"
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise vol.Invalid(message)
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as err:
        raise vol.Invalid(message) from err
    if not math.isfinite(result) or result <= 0:
        raise vol.Invalid(message)
    return result


def settings(options):
    return {
        ENABLED: options.get(ENABLED, False) is True,
        **{key: coefficient(options.get(key)) for key in COEFFICIENTS},
    }


def _valid_total(value):
    """Reject malformed or unrepresentably large persisted totals."""
    if type(value) not in (int, float) or value < 0:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _validate_stored(stored):
    """Validate before calling Store, which may otherwise migrate or rename."""
    if (
        not isinstance(stored, dict)
        or not _valid_total(stored.get("kg"))
        or not isinstance(stored.get("previous"), list)
        or len(stored["previous"]) != 5
        or any(
            v is not None and (type(v) is not int or v < 0) for v in stored["previous"]
        )
        or not isinstance(stored.get("reasons"), list)
        or not all(isinstance(v, str) for v in stored["reasons"])
        or not isinstance(stored.get("settings"), dict)
    ):
        raise InvalidPelletStorageError
    try:
        valid_settings = settings(stored["settings"])
    except vol.Invalid as err:
        raise InvalidPelletStorageError from err
    if valid_settings != stored["settings"]:
        raise InvalidPelletStorageError


class PelletEstimate:
    """Persist amount and baselines together, before exposing each update.

    All mutations are serialized, including option boundaries and unload.
    Missing readings retain the last valid baseline. A settings change instead
    drops all baselines: the first subsequent reading is explicitly unestimated.
    """

    def __init__(self, hass, entry_id):
        self.hass = hass
        self.store = Store(hass, 1, f"edilkamin_pellet_{entry_id}")
        self.lock = asyncio.Lock()
        self.closed = False
        self.storage_invalid = False
        self._disk_state = None
        self.state = {
            "kg": 0.0,
            "previous": [None] * 5,
            "settings": settings({}),
            "reasons": [],
        }

    @property
    def enabled(self):
        return self.state["settings"][ENABLED]

    @property
    def incomplete(self):
        return bool(self.state["reasons"])

    async def async_load(self, options):
        """Restore using HA Store; invalid storage must not fabricate a total."""
        # Store normally renames malformed JSON and returns None. For an
        # accumulator that would silently lose history, so fail before loading.
        existing = await self.hass.async_add_executor_job(self._read_existing)
        if existing is not None:
            _validate_stored(existing["data"])
            self._disk_state = deepcopy(existing["data"])
        stored = await self.store.async_load()
        if (existing is None and stored is not None) or (
            existing is not None and stored != existing["data"]
        ):
            raise InvalidPelletStorageError
        if stored is not None:
            self.state = stored
        await self.async_configure(options)

    def _read_existing(self):
        try:
            with Path(self.store.path).open(encoding="utf-8") as stored:
                existing = json.load(stored)
        except FileNotFoundError:
            return None
        except (OSError, ValueError, UnicodeDecodeError) as err:
            raise InvalidPelletStorageError from err
        if (
            not isinstance(existing, dict)
            or not existing
            or existing.get("data") is None
            or type(existing.get("version")) is not int
            or existing["version"] != 1
            or type(existing.get("minor_version", 1)) is not int
            or existing.get("minor_version", 1) != 1
        ):
            raise InvalidPelletStorageError
        return existing

    async def _commit(self, state):
        # Keep the transaction lock until disk work finishes even if HA cancels
        # the refresh. A detached executor write must not race the next runtime.
        task = asyncio.create_task(self._write_and_commit(state))
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            await task
            raise

    async def _write_and_commit(self, state):
        # A failed disk write leaves the previous in-memory transaction intact.
        try:
            await self.hass.async_add_executor_job(self._check_disk)
        except InvalidPelletStorageError:
            self.storage_invalid = True
            _LOGGER.exception(
                "Pellet estimate storage changed or became invalid; "
                "preserving the file and stopping the estimate"
            )
            raise
        await self.store.async_save(state)
        # HA Store logs and swallows WriteError. Confirm the transaction reached
        # disk before publishing it, rather than relying on async_save's return.
        await self.hass.async_add_executor_job(self._verify_saved, state)
        self.state = state
        self._disk_state = deepcopy(state)

    def _check_disk(self):
        existing = self._read_existing()
        disk_state = None if existing is None else existing["data"]
        if disk_state != self._disk_state:
            raise InvalidPelletStorageError

    def _verify_saved(self, expected):
        with Path(self.store.path).open(encoding="utf-8") as stored:
            actual = json.load(stored)
        if actual.get("data") != expected:
            message = "Pellet estimate storage write was not persisted"
            raise OSError(message)

    async def async_configure(self, options):
        """Apply settings via an explicit, conservative unestimated boundary."""
        new = settings(options)
        async with self.lock:
            if self.storage_invalid:
                if new[ENABLED]:
                    raise InvalidPelletStorageError
                return
            if self.closed or new == self.state["settings"]:
                return
            state = deepcopy(self.state)
            if self.enabled and new[ENABLED]:
                state["reasons"] = sorted(set(state["reasons"]) | {"calibration_gap"})
            state["settings"] = new
            state["previous"] = [None] * 5
            await self._commit(state)

    async def async_update(self, coordinator):  # noqa: C901, PLR0912
        # One transaction intentionally keeps all five baselines and kg atomic.
        """Consume only validated cumulative hours from this device coordinator."""
        async with self.lock:
            if self.closed or self.storage_invalid or not self.enabled:
                return
            state = deepcopy(self.state)
            reasons = set(state["reasons"])
            for index, key in enumerate(COEFFICIENTS):
                current = coordinator.get_working_hours(index + 1)
                previous = state["previous"][index]
                if current is None:
                    continue
                state["previous"][index] = current
                if previous is None:
                    continue
                delta = current - previous
                if delta < 0:
                    reasons.add(f"p{index + 1}_counter_reset")
                elif delta > 0:
                    rate = state["settings"][key]
                    if rate is None:
                        reasons.add(f"p{index + 1}_uncalibrated")
                    else:
                        try:
                            total = state["kg"] + delta * rate
                        except OverflowError:
                            total = math.inf
                        if math.isfinite(total):
                            state["kg"] = total
                        else:
                            reasons.add("numeric_overflow")
            state["reasons"] = sorted(reasons)
            if state != self.state:
                try:
                    await self._commit(state)
                except InvalidPelletStorageError:
                    # Keep device refreshes working; the estimate is unavailable
                    # until the preserved file is restored and the entry reloads.
                    return

    async def async_flush(self):
        """Wait for any in-flight transaction before releasing this runtime."""
        async with self.lock:
            self.closed = True  # Ignore late coordinator responses after unload.
