"""Config flow for Edilkamin integration."""

from __future__ import annotations

import logging
from typing import Any

from custom_components.edilkamin.api.edilkamin_async_api import EdilkaminAsyncApi
import macaddress
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, MAC_ADDRESS, PASSWORD, USERNAME

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(MAC_ADDRESS): str,
        vol.Required(USERNAME): str,
        vol.Required(PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Edilkamin."""

    VERSION = 2

    async def async_step_user(self, user_input):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mac_address = user_input[MAC_ADDRESS]

            try:
                macaddress.MAC(mac_address)
            except ValueError as error:
                _LOGGER.error("Invalid mac address: %s", error)
                errors["base"] = "mac_address"
                return self.async_show_form(
                    step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
                )

            username = user_input[USERNAME]
            password = user_input[PASSWORD]
            api = EdilkaminAsyncApi(
                mac_address=mac_address,
                username=username,
                password=password,
                hass=self.hass,
            )
            try:
                await api.authenticate()
            except Exception as exception:  # noqa: BLE001
                exception_type = type(exception).__name__
                _LOGGER.error("Exception type: %s", exception_type)
                _LOGGER.error("Exception message: %s", exception)
                if exception.__class__.__name__ == "NotAuthorizedException":
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=mac_address.replace(":", ""), data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class InvalidMacAddress(HomeAssistantError):
    """Error to indicate there is invalid mac address."""
