"""Config flow for Edilkamin integration."""
from __future__ import annotations

import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from custom_components.edilkamin.api.edilkamin_async_api import (
    EdilkaminAsyncApi,
    HttpException,
)

from typing import Any

from .const import DOMAIN, MAC_ADDRESS, REFRESH_TOKEN, CLIENT_ID

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(MAC_ADDRESS): str, vol.Required(CLIENT_ID): str, vol.Required(REFRESH_TOKEN): str}
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    mac_address = data[MAC_ADDRESS]
    refresh_token = data[REFRESH_TOKEN]
    client_id = data[CLIENT_ID]

    api = EdilkaminAsyncApi(
        mac_address=mac_address,
        session=async_get_clientsession(hass),
        refresh_token=refresh_token,
        client_id=client_id
    )

    try:
        await api.check()
    except HttpException:
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"title": mac_address.replace(":", "")}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Edilkamin."""

    VERSION = 1


    async def async_step_user(self, user_input):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidMacAddress:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidMacAddress(HomeAssistantError):
    """Error to indicate there is invalid mac address."""
