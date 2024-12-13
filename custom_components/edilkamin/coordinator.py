from datetime import timedelta
import logging

import async_timeout

import edilkamin
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from custom_components.edilkamin.api.edilkamin_async_api import EdilkaminAsyncApi

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
            update_interval=timedelta(seconds=240),
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
            async with async_timeout.timeout(10):
                self._device_info = await self.update_device_information()
                _LOGGER.debug("Data updated successfully")
                _LOGGER.debug(self._device_info)
                return self._device_info
        except Exception as err:
            raise UpdateFailed("Error communicating with API") from err

    def get_token(self):
        """Return the current token."""
        return self._token

    def get_mac_address(self):
        """Return the MAC address."""
        return self._mac_address

    def get_temperature(self):
        """Get the temperature."""
        return self._device_info.get("status").get("temperatures").get("enviroment")
