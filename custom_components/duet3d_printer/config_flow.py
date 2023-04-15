"""Config flow for Duet3D Printer integration."""
from homeassistant import config_entries
import logging
from typing import Any, Dict, Optional
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .schema import CONFIG_SCHEMA
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PATH,
)

from .const import (
    CONF_NUMBER_OF_TOOLS,
    CONF_BED,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _schema_with_defaults(
    host="", port=80, path="/machine/status", no_of_tools=1, has_bad=True
):
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_PORT, default=port): cv.port,
            vol.Required(CONF_PATH, default=path): str,
            vol.Required(CONF_NUMBER_OF_TOOLS, default=no_of_tools): vol.Schema(
                cv.positive_int
            ),
            vol.Optional(CONF_BED, default=has_bad): bool,
        },
        extra=vol.ALLOW_EXTRA,
    )


class Duet3dConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Duet3DPrinter."""

    VERSION = 1
    _LOGGER.critical("Entering config flow")

    def __init__(self) -> None:
        """Handle a config flow for OctoPrint."""
        self.discovery_schema = None
        self._user_input = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        # When coming back from the progress steps, the user_input is stored in the
        # instance variable instead of being passed in
        if user_input is None and self._user_input:
            user_input = self._user_input

        if user_input is None:
            data = self.discovery_schema or _schema_with_defaults()
            return self.async_show_form(step_id="user", data_schema=data)

    async def _finish_config(self, user_input: dict):
        """Finish the configuration setup."""
        existing_entry = await self.async_set_unique_id(self.unique_id)
        if existing_entry is not None:
            self.hass.config_entries.async_update_entry(existing_entry, data=user_input)
            # Reload the config entry otherwise devices will remain unavailable
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )

            return self.async_abort(reason="reauth_successful")
        return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

    async def async_step_import(self, user_input):
        """Handle import."""
        return await self.async_step_user(user_input)
