"""Config flow for Edilkamin integration."""

from __future__ import annotations

import logging

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
import macaddress
import voluptuous as vol

from custom_components.edilkamin.api.edilkamin_async_api import EdilkaminAsyncApi

from .const import DOMAIN, MAC_ADDRESS, PASSWORD, USERNAME
from .pellet import (
    COEFFICIENTS,
    ENABLED,
    InvalidPelletStorageError,
    PelletEstimate,
    entry_lock,
    settings,
)

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

    @staticmethod
    @callback
    def async_get_options_flow(_config_entry):
        return PelletOptionsFlow()

    async def async_step_user(self, user_input):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mac_address = user_input[MAC_ADDRESS]

            try:
                macaddress.MAC(mac_address)
            except ValueError:
                _LOGGER.exception("Invalid mac address: %s", mac_address)
                errors["base"] = "mac_address"
                return self.async_show_form(
                    step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
                )

            # Check if a stove with the same mac address is already configured
            await self.async_set_unique_id(mac_address)
            self._abort_if_unique_id_configured()

            username = user_input[USERNAME]
            password = user_input[PASSWORD]
            api = EdilkaminAsyncApi(
                mac_address=mac_address,
                username=username,
                password=password,
                hass=self.hass,
            )
            try:
                if await api.authenticate():
                    return self.async_create_entry(
                        title=mac_address.replace(":", ""), data=user_input
                    )

                errors["base"] = "invalid_auth"
            except Exception as exception:
                _LOGGER.exception("Exception message: %s, type=%s")
                if exception.__class__.__name__ == "NotAuthorizedException":
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class PelletOptionsFlow(config_entries.OptionsFlow):
    """Optional user calibration, with no universal coefficients."""

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                validated = settings(user_input)
            except vol.Invalid:
                errors["base"] = "invalid_coefficient"
            else:
                entry = self.config_entry
                async with entry_lock(self.hass, entry.entry_id):
                    coordinator = (
                        self.hass.data[DOMAIN]
                        .get("coordinators", {})
                        .get(entry.entry_id)
                    )
                    estimate = coordinator.pellet if coordinator is not None else None
                    try:
                        if estimate is None:
                            estimate = PelletEstimate(self.hass, entry.entry_id)
                            await estimate.async_load(entry.options)
                        await estimate.async_configure(validated)
                    except InvalidPelletStorageError:
                        # Disabling must remain possible without modifying a
                        # damaged file. Re-enabling requires a restored backup;
                        # loading while disabled records the missed boundary.
                        if validated[ENABLED]:
                            errors["base"] = "invalid_pellet_storage"
                        else:
                            return self.async_create_entry(title="", data=validated)
                    else:
                        return self.async_create_entry(title="", data=validated)

        options = self.config_entry.options
        schema = {vol.Required(ENABLED, default=options.get(ENABLED, False)): bool}
        for key in COEFFICIENTS:
            schema[
                vol.Optional(
                    key,
                    description={
                        "suggested_value": str(options[key])
                        if options.get(key) is not None
                        else ""
                    },
                )
            ] = str
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema), errors=errors
        )


class InvalidMacAddressError(HomeAssistantError):
    """Error to indicate there is invalid mac address."""
