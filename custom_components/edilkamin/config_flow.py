"""Config flow for Edilkamin integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.edilkamin.api.edilkamin_async_api import (
    EdilkaminAsyncApi,
)
from .const import DOMAIN, MAC_ADDRESS, USERNAME, PASSWORD

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(MAC_ADDRESS): str,
        vol.Required(USERNAME): str,
        vol.Required(PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    mac_address = data[MAC_ADDRESS]
    username = data[USERNAME]
    password = data[PASSWORD]

    api = EdilkaminAsyncApi(
        mac_address=mac_address, username=username, password=password, hass=hass
    )

    if not await api.authenticate():
        raise InvalidAuth

    # Return info that you want to store in the config entry.
    return {"title": mac_address.replace(":", "")}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Edilkamin."""

    VERSION = 2

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

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidMacAddress(HomeAssistantError):
    """Error to indicate there is invalid mac address."""
