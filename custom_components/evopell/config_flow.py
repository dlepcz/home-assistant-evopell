"""Config flow for Evopell integration."""

from __future__ import annotations

import ipaddress
import re

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_EVOPELL_PASSWORD,
    CONF_EVOPELL_USER,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_EVOPELL_USER): str,
        vol.Required(CONF_EVOPELL_PASSWORD): str,
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EVOPELL_USER): str,
        vol.Required(CONF_EVOPELL_PASSWORD): str,
        vol.Required(CONF_SCAN_INTERVAL): int,
    }
)


def host_valid(host: str) -> bool:
    """Return True if hostname or IP address is valid."""
    try:
        if ipaddress.ip_address(host).version == 4:
            return True
    except ValueError:
        disallowed = re.compile(r"[^a-zA-Z\d\-]")
        return all(x and not disallowed.search(x) for x in host.split("."))

    return False


@callback
def evopell_entries(hass: HomeAssistant) -> set[str]:
    """Return the hosts already configured."""
    return {
        entry.data[CONF_HOST] for entry in hass.config_entries.async_entries(DOMAIN)
    }


class EltermProxyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Evopell integration."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def _host_in_configuration_exists(self, host: str) -> bool:
        return host in evopell_entries(self.hass)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            if self._host_in_configuration_exists(host):
                errors[CONF_HOST] = "already_configured"
            elif not host_valid(host):
                errors[CONF_HOST] = "invalid_host"
            else:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return EvopellOptionsFlow(config_entry)


class EvopellOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Evopell integration (edit in UI)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Init options flow."""
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = {
            CONF_EVOPELL_USER: self._entry.options.get(
                CONF_EVOPELL_USER, self._entry.data.get(CONF_EVOPELL_USER, "")
            ),
            CONF_EVOPELL_PASSWORD: self._entry.options.get(
                CONF_EVOPELL_PASSWORD, self._entry.data.get(CONF_EVOPELL_PASSWORD, "")
            ),
            CONF_SCAN_INTERVAL: self._entry.options.get(
                CONF_SCAN_INTERVAL,
                self._entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ),
        }

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_EVOPELL_USER, default=defaults[CONF_EVOPELL_USER]
                ): str,
                vol.Required(
                    CONF_EVOPELL_PASSWORD, default=defaults[CONF_EVOPELL_PASSWORD]
                ): str,
                vol.Required(
                    CONF_SCAN_INTERVAL, default=defaults[CONF_SCAN_INTERVAL]
                ): int,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
