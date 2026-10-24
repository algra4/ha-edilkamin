"""Read-only daily chrono schedule from the existing cloud coordinator."""

from typing import ClassVar

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN


class EdilkaminDailyScheduleSensor(CoordinatorEntity, SensorEntity):
    """Expose today's 48 half-hour slots without additional cloud requests."""

    _attr_name = "Daily schedule"
    _attr_icon = "mdi:chart-timeline-variant"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = ["enabled", "disabled"]

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        mac_address = coordinator.get_mac_address()
        self._attr_unique_id = f"{mac_address}_daily_schedule"
        self._attr_device_info = {"identifiers": {(DOMAIN, mac_address)}}

    def _schedule(self):
        """Validate the selected weekly schedule; missing data is not an off plan."""
        data = self.coordinator.data
        nvm = data.get("nvm") if isinstance(data, dict) else None
        if not isinstance(nvm, dict):
            return None
        chrono = nvm.get("chrono")
        parameters = nvm.get("user_parameters")
        if not isinstance(chrono, dict) or not isinstance(parameters, dict):
            return None
        is_auto = parameters.get("is_auto")
        active = chrono.get("is_active")
        if any(
            type(flag) not in (bool, int) or flag not in (0, 1)
            for flag in (is_auto, active)
        ):
            return None
        key = "temperature_ranges" if is_auto else "power_ranges"
        values = chrono.get(key)
        if not isinstance(values, list) or len(values) != 336:
            return None
        maximum = 2 if is_auto else 5
        if any(type(value) is not int or not 0 <= value <= maximum for value in values):
            return None
        return chrono, bool(is_auto), values

    @property
    def available(self) -> bool:
        return super().available and self._schedule() is not None

    @property
    def native_value(self) -> str | None:
        schedule = self._schedule()
        if schedule is None:
            return None
        return "enabled" if schedule[0]["is_active"] else "disabled"

    @property
    def extra_state_attributes(self) -> dict:
        schedule = self._schedule()
        if schedule is None:
            return {}
        chrono, is_auto, values = schedule
        now = dt_util.now()
        start = now.weekday() * 48
        return {
            "date": now.date().isoformat(),
            "timezone": str(dt_util.DEFAULT_TIME_ZONE),
            "slots": values[start : start + 48],
            "chrono_active": bool(chrono["is_active"]),
            "is_auto": is_auto,
            "economy_temperature": chrono.get("economy_temperature"),
            "comfort_temperature": chrono.get("comfort_temperature"),
        }
