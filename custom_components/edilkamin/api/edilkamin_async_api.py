import logging

import edilkamin
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class EdilkaminAsyncApi:
    """Class to interact with the Edilkamin API."""

    def __init__(
        self, mac_address, username: str, password: str, hass: HomeAssistant
    ) -> None:
        """Initialize the class."""
        self._hass = hass
        self._mac_address = mac_address
        self._username = username
        self._password = password

    def get_mac_address(self):
        """Get the mac address."""
        return self._mac_address

    async def authenticate(self) -> bool:
        try:
            await self._hass.async_add_executor_job(
                edilkamin.sign_in, self._username, self._password
            )
        except Exception:  # noqa: BLE001
            return False
        else:
            return True

    async def set_temperature(self, value):
        """Modify the temperature."""
        await self.execute_command({"name": "enviroment_1_temperature", "value": value})

    async def enable_power(self):
        """Set the power status to on."""
        await self.execute_command({"name": "power", "value": 1})

    async def disable_power(self):
        """Set the power status to off."""
        await self.execute_command({"name": "power", "value": 0})

    async def enable_chrono_mode(self):
        """Enable the chrono mode."""
        await self.execute_command({"name": "chrono_mode", "value": True})

    async def disable_chrono_mode(self):
        """Disable the chono mode."""
        await self.execute_command({"name": "chrono_mode", "value": False})

    async def enable_airkare(self):
        """Enable airkare."""
        await self.execute_command({"name": "airkare_function", "value": 1})

    async def disable_airkare(self):
        """Disable airkare."""
        await self.execute_command({"name": "airkare_function", "value": 0})

    async def enable_relax(self):
        """Enable relax."""
        await self.execute_command({"name": "relax_mode", "value": True})

    async def disable_relax(self):
        """Disable relax."""
        await self.execute_command({"name": "relax_mode", "value": False})

    async def set_fan_speed(self, value, index=1):
        """Set the speed of fan 1."""
        await self.execute_command(
            {"name": "fan_" + str(index) + "_speed", "value": int(value)}
        )

    async def check(self):
        """Call check config."""
        await self.execute_command({"name": "check", "value": False})

    async def get_token(self):
        return await self._hass.async_add_executor_job(
            edilkamin.sign_in, self._username, self._password
        )

    async def get_info(self):
        """Get the device information."""
        token = await self.get_token()
        return await self._hass.async_add_executor_job(
            edilkamin.device_info, token, self._mac_address
        )

    async def enable_standby_mode(self):
        """Set the standby mode."""
        if not await self.is_auto():
            raise NotInRightStateError

        await self.execute_command({"name": "standby_mode", "value": True})

    async def disable_standby_mode(self):
        """Set the standby mode."""
        if not await self.is_auto():
            raise NotInRightStateError

        await self.execute_command({"name": "standby_mode", "value": False})

    async def is_auto(self):
        """Check if the device is in auto mode."""
        return (await self.get_info()).get("nvm").get("user_parameters").get("is_auto")

    async def enable_auto_mode(self):
        """Set the auto mode."""
        await self.execute_command({"name": "auto_mode", "value": True})

    async def disable_auto_mode(self):
        """Set the auto mode."""
        await self.execute_command({"name": "auto_mode", "value": False})

    async def set_manual_power_level(self, value: int):
        """Set the manual power level."""
        await self.execute_command({"name": "power_level", "value": value})

    async def execute_command(self, payload: dict) -> str:
        """Execute the command."""
        token = await self.get_token()
        _LOGGER.debug("Execute command with payload = %s", payload)
        return await self._hass.async_add_executor_job(
            edilkamin.mqtt_command, token, self._mac_address, payload
        )


class HttpError(Exception):
    """HTTP exception class with message text, and status code."""

    def __init__(self, message, text, status_code) -> None:
        """Initialize the class."""
        super().__init__(message)
        self.status_code = status_code
        self.text = text


class EdilkaminApiError(Exception):
    """Base class for exceptions in this module."""


class NotInRightStateError(EdilkaminApiError):
    """Exception raised when the device is not in the right state."""

    def __init__(self):
        super().__init__("Standby mode is only available from auto mode.")
