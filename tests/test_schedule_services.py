"""Device routing, schema validation and action lifecycle with real HA calls."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import pytest
import voluptuous as vol

from custom_components.edilkamin.const import DOMAIN
from custom_components.edilkamin.schedule_services import (
    async_setup_services,
    async_unload_services,
)


@pytest.mark.asyncio
async def test_device_selection_routes_to_exact_entry_and_unloads(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.data[DOMAIN] = {}
    entries = [SimpleNamespace(entry_id="first"), SimpleNamespace(entry_id="second")]
    info = {
        "nvm": {
            "user_parameters": {"is_auto": True},
            "chrono": {
                "is_active": True,
                "temperature_ranges": [0] * 336,
                "power_ranges": [0] * 336,
                "economy_temperature": 20,
                "comfort_temperature": 22,
            },
        }
    }
    apis = [
        Mock(
            get_info=AsyncMock(return_value=deepcopy(info)), execute_command=AsyncMock()
        )
        for _ in entries
    ]
    coordinators = [Mock(async_request_refresh=AsyncMock()) for _ in entries]
    for entry, api, coordinator in zip(entries, apis, coordinators, strict=True):
        await async_setup_services(hass, entry, api, coordinator)
    registry = Mock()
    registry.async_get.side_effect = (
        lambda device_id: SimpleNamespace(config_entries={device_id})
        if device_id in {"first", "second"}
        else None
    )
    request = {
        "device_id": "second",
        "days": ["tuesday"],
        "start": "23:30",
        "end": "24:00",
        "mode": "comfort",
        "preview_only": True,
    }
    with patch(
        "custom_components.edilkamin.schedule_services.dr.async_get",
        return_value=registry,
    ):
        result = await hass.services.async_call(
            DOMAIN, "set_schedule", request, blocking=True, return_response=True
        )
        assert result["status"] == "preview"
        assert result["changed_slots"] == [95]
        apis[0].get_info.assert_not_called()
        apis[1].get_info.assert_awaited_once()
        once = await hass.services.async_call(
            DOMAIN,
            "set_schedule",
            {**request, "auto_restore": True},
            blocking=True,
            return_response=True,
        )
        assert once["recurrence"] == "once"
        assert once["restore_at"]
        assert not hass.data[DOMAIN]["schedule_writers"]["second"].windows
        for api in apis:
            api.execute_command.assert_not_called()
        for malformed in [[], ["first", "second"]]:
            with pytest.raises((vol.Invalid, ServiceValidationError)):
                await hass.services.async_call(
                    DOMAIN,
                    "set_schedule",
                    {**request, "device_id": malformed},
                    blocking=True,
                )
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                "set_schedule",
                {**request, "device_id": "unknown"},
                blocking=True,
            )
        await async_unload_services(hass, entries[1])
        assert hass.services.has_service(DOMAIN, "set_schedule")
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN, "set_schedule", request, blocking=True
            )
        await async_unload_services(hass, entries[0])
        assert not hass.services.has_service(DOMAIN, "set_schedule")


@pytest.mark.asyncio
async def test_ambiguous_device_and_invalid_time_do_not_read_or_write(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.data[DOMAIN] = {}
    entries = [SimpleNamespace(entry_id="first"), SimpleNamespace(entry_id="second")]
    api = Mock(get_info=AsyncMock(), execute_command=AsyncMock())
    for entry in entries:
        await async_setup_services(hass, entry, api, Mock())
    registry = Mock(
        async_get=Mock(return_value=SimpleNamespace(config_entries={"first", "second"}))
    )
    request = {
        "device_id": "device",
        "days": ["monday"],
        "start": "06:00",
        "end": "07:00",
        "mode": "economy",
    }
    with patch(
        "custom_components.edilkamin.schedule_services.dr.async_get",
        return_value=registry,
    ):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN, "set_schedule", request, blocking=True
            )
        with pytest.raises((vol.Invalid, ServiceValidationError)):
            await hass.services.async_call(
                DOMAIN, "set_schedule", {**request, "end": "06:15"}, blocking=True
            )
    api.get_info.assert_not_called()
    api.execute_command.assert_not_called()
    for entry in entries:
        await async_unload_services(hass, entry)
