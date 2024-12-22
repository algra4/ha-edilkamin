from datetime import timedelta
import logging

import async_timeout
from custom_components.edilkamin.api.edilkamin_async_api import EdilkaminAsyncApi

import edilkamin
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class EdilkaminCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(
        self,
        hass,
        username: str,
        password: str,
        mac_address: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Edilkamin coordinator",
            update_interval=timedelta(seconds=15),
        )
        self._username = username
        self._password = password
        self._mac_address = mac_address

        self._token = None
        self._device_info = {}
        self._edilkamin_wrapper = EdilkaminAsyncApi(
            mac_address=mac_address, username=username, password=password, hass=hass
        )

    async def refresh_token(self) -> str:
        """Login to refresh the token."""
        return await self.hass.async_add_executor_job(
            edilkamin.sign_in, self._username, self._password
        )

    async def update_device_information(self) -> None:
        """Get the latest data and update the relevant Entity attributes."""
        self._token = await self.refresh_token()
        return await self.hass.async_add_executor_job(
            edilkamin.device_info, self._token, self._mac_address
        )

    async def _async_update_data(self):
        """Fetch data from the API."""
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                self._device_info = await self.update_device_information()
                _LOGGER.debug("Data updated successfully")
                _LOGGER.debug(self._device_info)
                return self._device_info
        except Exception:
            raise UpdateFailed("Error communicating with API")

    def get_token(self) -> str:
        """Return the current token."""
        return self._token

    def get_mac_address(self) -> str:
        """Return the MAC address."""
        return self._mac_address

    def get_temperature(self) -> str:
        """Get the temperature."""
        return self._device_info.get("status").get("temperatures").get("enviroment")

    def get_fan_speed(self, index: int = 1) -> str:
        """Get the fan speed."""

        return (
            self._device_info.get("nvm")
            .get("user_parameters")
            .get("fan_" + str(index) + "_ventilation")
        )

    def get_nb_fans(self):
        """Get the number of fans."""
        return (
            self._device_info.get("nvm").get("installer_parameters").get("fans_number")
        )

    def get_nb_alarms(self) -> str:
        """Get the number of alarms."""
        return self._device_info.get("nvm").get("alarms_log").get("index")

    def get_alarms(self) -> list:
        """Get the alarms."""
        alarms_info = self._device_info.get("nvm").get("alarms_log")
        index = alarms_info.get("index")
        return [alarms_info.get("alarms")[i] for i in range(index)]

    def get_actual_power(self) -> str:
        """Get the actual power."""
        return self._device_info.get("status").get("state").get("actual_power")

    def get_status_tank(self) -> str:
        """Get the status of the tank."""
        return self._device_info.get("status").get("flags").get("is_pellet_in_reserve")

    def get_airkare_status(self) -> str:
        """Get the status of the airkare."""
        return self._device_info.get("status").get("flags").get("is_airkare_active")

    def get_power_status(self) -> str:
        """Get the status of the power."""
        return self._device_info.get("status").get("commands").get("power")

    def get_relax_status(self) -> str:
        """Get the status of the relax."""
        return self._device_info.get("status").get("flags").get("is_relax_active")

    def get_target_temperature(self) -> str:
        """Get the target temperature."""
        return (
            self._device_info.get("nvm")
            .get("user_parameters")
            .get("enviroment_1_temperature")
        )

    def get_chrono_mode_status(self) -> str:
        """Get the status of the chrono mode."""
        return self._device_info.get("nvm").get("chrono").get("is_active")

    def get_operational_phase(self) -> str:
        """Get the operational phase."""
        return self._device_info.get("status").get("state").get("operational_phase")

    def get_autonomy_second(self) -> str:
        """Get the operational phase."""
        return self._device_info.get("status").get("pellet").get("autonomy_time")
