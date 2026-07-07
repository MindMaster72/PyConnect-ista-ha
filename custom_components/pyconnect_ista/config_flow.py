"""Config flow for the ista Connect integration."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pyconnect_ista import IstaConnectClient
from pyconnect_ista.exceptions import AuthenticationError, IstaConnectException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import NumberSelector, NumberSelectorConfig, NumberSelectorMode

from .const import CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)


class CannotConnect(Exception):
    """Raised when the integration cannot connect to istaConnect."""


class InvalidAuth(Exception):
    """Raised when istaConnect rejects the credentials."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate user credentials by logging into istaConnect."""
    client = IstaConnectClient()

    try:
        await client.login(data[CONF_EMAIL], data[CONF_PASSWORD])
    except AuthenticationError as err:
        raise InvalidAuth from err
    except (httpx.HTTPError, IstaConnectException) as err:
        raise CannotConnect from err
    finally:
        await client.close()

    return {"title": data[CONF_EMAIL]}


def _user_schema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    """Return config flow schema."""
    user_input = user_input or {}
    return vol.Schema(
        {
            vol.Required(CONF_EMAIL, default=user_input.get(CONF_EMAIL, "")): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(
                CONF_UPDATE_INTERVAL,
                default=user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            ): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.SLIDER, min=1, max=24)),
        }
    )


class PyConnectIstaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ista Connect."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return PyConnectIstaOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during ista Connect config flow")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"{NAME} {info['title']}",
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                    options={
                        CONF_UPDATE_INTERVAL: user_input[CONF_UPDATE_INTERVAL],
                    },
                )

        return self.async_show_form(step_id="user", data_schema=_user_schema(user_input), errors=errors)


class PyConnectIstaOptionsFlow(config_entries.OptionsFlow):
    """Handle options for ista Connect."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self._config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                    ): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.SLIDER, min=1, max=24)),
                }
            ),
        )
