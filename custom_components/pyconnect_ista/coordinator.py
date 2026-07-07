"""Data coordinator for the ista Connect integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import httpx
from pyconnect_ista import IstaConnectClient
from pyconnect_ista.exceptions import AuthenticationError, IstaConnectException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEVICE_SERIES_ENDPOINTS = {
    "heat_devices_month": "/user/{user_id}/consumption/devices/HEAT/DEVICE_UNIT/MONTH",
    "heat_devices_day": "/user/{user_id}/consumption/devices/HEAT/DEVICE_UNIT/DAY",
    "hot_water_devices_month": "/user/{user_id}/consumption/devices/HOT_WATER/M_3/MONTH",
    "hot_water_devices_day": "/user/{user_id}/consumption/devices/HOT_WATER/M_3/DAY",
    "cold_water_devices_month": "/user/{user_id}/consumption/devices/COLD_WATER/M_3/MONTH",
    "cold_water_devices_day": "/user/{user_id}/consumption/devices/COLD_WATER/M_3/DAY",
}


class PyConnectIstaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate istaConnect data updates."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.config_entry = entry
        self.client = IstaConnectClient()

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{entry.entry_id}",
            update_interval=timedelta(hours=entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)),
        )

    async def _async_setup(self) -> None:
        """Log in before the first refresh."""
        try:
            await self._async_login()
        except AuthenticationError as err:
            await self.client.close()
            raise ConfigEntryAuthFailed("Invalid istaConnect credentials") from err
        except Exception as err:
            await self.client.close()
            raise ConfigEntryNotReady("Could not log in to istaConnect") from err

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from istaConnect."""
        try:
            return await self._async_fetch_data()
        except AuthenticationError:
            _LOGGER.debug("istaConnect session expired; trying a clean login")
            await self._async_reset_client()
            try:
                return await self._async_fetch_data()
            except AuthenticationError as err:
                raise ConfigEntryAuthFailed("Invalid istaConnect credentials") from err
            except IstaConnectException as err:
                raise UpdateFailed(f"istaConnect rejected the refreshed session: {err}") from err
        except IstaConnectException as err:
            _LOGGER.debug("istaConnect request failed; retrying with a clean session: %s", err)
            await self._async_reset_client()
            try:
                return await self._async_fetch_data()
            except IstaConnectException as retry_err:
                raise UpdateFailed(f"Error updating istaConnect data after reconnect: {retry_err}") from retry_err
        except httpx.HTTPError as err:
            raise UpdateFailed(f"Error communicating with istaConnect: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error while updating istaConnect data: {err}") from err

    async def async_close(self) -> None:
        """Close the underlying API client."""
        await self.client.close()

    async def _async_device_series(self) -> dict[str, Any]:
        """Fetch per-device consumption series."""
        data: dict[str, Any] = {}
        for key, endpoint in DEVICE_SERIES_ENDPOINTS.items():
            data[key] = await self.client._api.get(endpoint.format(user_id=self.client.user_id))
        return data

    async def _async_login(self) -> None:
        """Log in to istaConnect with the config entry credentials."""
        await self.client.login(self.config_entry.data[CONF_EMAIL], self.config_entry.data[CONF_PASSWORD])

    async def _async_reset_client(self) -> None:
        """Drop the current client and create a clean session."""
        await self.client.close()
        self.client = IstaConnectClient()

    async def _async_fetch_data(self) -> dict[str, Any]:
        """Fetch all data, logging in first when needed."""
        if not self.client.authenticated:
            await self._async_login()

        return {
            "user": self.client.user,
            "user_id": self.client.user_id,
            "latest": await self.client.latest_consumption(),
            "series": {
                "heat_month": await self.client.heat_month(),
                "heat_day": await self.client.heat_day(),
                "hot_water_month": await self.client.hot_water_month(),
                "hot_water_day": await self.client.hot_water_day(),
                "cold_water_month": await self.client.cold_water_month(),
                "cold_water_day": await self.client.cold_water_day(),
            },
            "device_series": await self._async_device_series(),
        }
