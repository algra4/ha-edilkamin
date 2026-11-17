"""Register one device-targeted schedule action for loaded config entries."""

from homeassistant.core import SupportsResponse
from homeassistant.helpers import config_validation as cv, device_registry as dr
import voluptuous as vol

from .const import DOMAIN
from .schedule_edit import EDIT_SCHEMA, ScheduleWriter, fail

WRITERS = "schedule_writers"
ACTION = "set_schedule"
TARGET_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): vol.All(
            cv.ensure_list, [cv.string], vol.Length(min=1, max=1)
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_services(hass, entry, api, coordinator):
    writers = hass.data[DOMAIN].setdefault(WRITERS, {})
    writer = ScheduleWriter(hass, api, coordinator, entry.entry_id)
    await writer.async_start()
    writers[entry.entry_id] = writer
    if hass.services.has_service(DOMAIN, ACTION):
        return

    async def handle(call):
        request = TARGET_SCHEMA(dict(call.data))
        device_id = request.pop("device_id")[0]
        device = dr.async_get(hass).async_get(device_id)
        if device is None:
            fail("Select one Edilkamin device with a loaded integration entry.")
        candidates = [
            writer
            for entry_id, writer in hass.data[DOMAIN][WRITERS].items()
            if entry_id in device.config_entries
        ]
        if len(candidates) != 1:
            fail("The selected device must have exactly one loaded Edilkamin entry.")
        return await candidates[0].set_schedule(request)

    def schema(data):
        request = TARGET_SCHEMA(dict(data))
        devices = request.pop("device_id")
        return {"device_id": devices, **EDIT_SCHEMA(request)}

    hass.services.async_register(
        DOMAIN,
        ACTION,
        handle,
        schema=vol.Schema(schema),
        supports_response=SupportsResponse.OPTIONAL,
    )


async def async_unload_services(hass, entry):
    writers = hass.data[DOMAIN].get(WRITERS, {})
    writer = writers.pop(entry.entry_id, None)
    if writer is not None:
        await writer.async_stop()
    if not writers:
        hass.services.async_remove(DOMAIN, ACTION)
