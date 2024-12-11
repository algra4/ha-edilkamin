import logging
import typing

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
            return True
        except Exception as exception:
            return False

    async def get_temperature(self):
        """Get the temperature."""
        _LOGGER.debug("Get temperature")
        result = (
            (await self.get_info()).get("status").get("temperatures").get("enviroment")
        )
        _LOGGER.debug("Get temperature response  = %s", result)
        return result

    async def set_temperature(self, value):
        """Modify the temperature."""
        _LOGGER.debug("Set temperature to = %s", value)
        await self.execute_command({"name": "enviroment_1_temperature", "value": value})

    async def get_power_status(self):
        """Get the power status."""
        _LOGGER.debug("Get power")
        result = (await self.get_info()).get("status").get("commands").get("power")
        _LOGGER.debug("Get power response  = %s", result)
        return result

    async def enable_power(self):
        """Set the power status to on."""
        _LOGGER.debug("Enable power")
        await self.execute_command({"name": "power", "value": 1})

    async def disable_power(self):
        """Set the power status to off."""
        _LOGGER.debug("Disable power")
        await self.execute_command({"name": "power", "value": 0})

    async def get_chrono_mode_status(self):
        """Get the status of the chrono mode."""
        _LOGGER.debug("Get the chrono mode")
        return (await self.get_info()).get("nvm").get("chrono").get("is_active")

    async def enable_chrono_mode(self):
        """Enable the chrono mode."""
        _LOGGER.debug("Enable chrono mode")
        await self.execute_command({"name": "chrono_mode", "value": True})

    async def disable_chrono_mode(self):
        """Disable the chono mode."""
        _LOGGER.debug("Disable chrono mode")
        await self.execute_command({"name": "chrono_mode", "value": False})

    async def get_airkare_status(self):
        """Get status of airekare."""
        _LOGGER.debug("Get airkare status")
        return (
            (await self.get_info()).get("status").get("flags").get("is_airkare_active")
        )

    async def enable_airkare(self):
        """Enable airkare."""
        _LOGGER.debug("Enable airkare")
        await self.execute_command({"name": "airkare_function", "value": 1})

    async def disable_airkare(self):
        """Disable airkare."""
        _LOGGER.debug("Disable airkare")
        await self.execute_command({"name": "airkare_function", "value": 0})

    async def get_relax_status(self):
        """Get the status of relax mode."""
        _LOGGER.debug("Get relax status")
        return (await self.get_info()).get("status").get("flags").get("is_relax_active")

    async def enable_relax(self):
        """Enable relax."""
        _LOGGER.debug("Enable relax")
        await self.execute_command({"name": "relax_mode", "value": True})

    async def disable_relax(self):
        """Disable relax."""
        _LOGGER.debug("Disable relax")
        await self.execute_command({"name": "relax_mode", "value": False})

    async def get_status_tank(self):
        """Get the status of the tank."""
        _LOGGER.debug("Get tank status")
        return (
            (await self.get_info())
            .get("status")
            .get("flags")
            .get("is_pellet_in_reserve")
        )

    async def get_fan_1_speed(self):
        """Get the speed of fan 1."""
        _LOGGER.debug("Get speed for fan 1")
        return (await self.get_info()).get("status").get("fans").get("fan_1_speed")

    async def set_fan_1_speed(self, value):
        """Set the speed of fan 1."""
        _LOGGER.debug("Set speed for fan 1 to %s", value)
        await self.execute_command({"name": "fan_1_speed", "value": value})

    async def check(self):
        """Call check config."""
        _LOGGER.debug("Check config")
        await self.execute_command({"name": "check", "value": False})

    async def get_target_temperature(self):
        """Get the target temperature."""
        _LOGGER.debug("Get the target temperature")
        return (
            (await self.get_info())
            .get("nvm")
            .get("user_parameters")
            .get("enviroment_1_temperature")
        )

    async def get_actual_power(self):
        """Get the power status."""
        _LOGGER.debug("Get power")
        return (await self.get_info()).get("status").get("state").get("actual_power")

    async def get_alarms(self):
        """Get the target temperature."""
        _LOGGER.debug("Get the target temperature")
        alarms_info = (await self.get_info()).get("nvm").get("alarms_log")
        index = alarms_info.get("index")
        alarms = []

        for i in range(index):
            alarms.append(alarms_info.get("alarms")[i])

        return alarms

    async def get_nb_alarms(self):
        """Get the target temperature."""
        _LOGGER.debug("Get the target temperature")
        return (await self.get_info()).get("nvm").get("alarms_log").get("index")

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

    async def execute_command(self, payload: dict) -> str:
        """Execute the command."""
        token = await self.get_token()
        return await self._hass.async_add_executor_job(
            edilkamin.mqtt_command, token, self._mac_address, payload
        )


class HttpException(Exception):
    """HTTP exception class with message text, and status code."""

    def __init__(self, message, text, status_code) -> None:
        """Initialize the class."""
        super().__init__(message)
        self.status_code = status_code
        self.text = text
