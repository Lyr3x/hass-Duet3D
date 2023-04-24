"""Config flow for Duet3D Printer integration."""
from homeassistant import config_entries
import logging
from typing import Any, Dict, Optional
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import hashlib
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
)

from .const import (
    CONF_NUMBER_OF_TOOLS,
    CONF_BED,
    CONF_MONITORED_CONDITIONS,
    DOMAIN,
    MONITORED_CONDITIONS,
    CONF_NAME,
    DEFAULT_NAME,
    CONF_API,
    CONF_GCODE_PATH,
    CONF_STATUS_PATH,
    CONF_BASE_URL,
    CONF_LIGHT,
    CONF_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _schema_with_defaults(
    name=DEFAULT_NAME,
    ssl=False,
    host="192.168.2.116",
    port=80,
    update_interval=30,
    number_of_tools=1,
    has_bed=True,
    has_light=False,
):
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=name): str,
            vol.Required(CONF_SSL, default=ssl): bool,
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_PORT, default=port): cv.port,
            vol.Required(CONF_INTERVAL, default=update_interval): int,
            vol.Required(CONF_NUMBER_OF_TOOLS, default=number_of_tools): vol.Schema(
                cv.positive_int
            ),
            vol.Optional(CONF_BED, default=has_bed): bool,
            vol.Optional(CONF_LIGHT, default=has_light): bool,
        },
        extra=vol.ALLOW_EXTRA,
    )


class Duet3dConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Duet3DPrinter."""

    VERSION = 1
    _LOGGER.debug("Entering config flow")

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_HOST],
                data={
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_SSL: user_input[CONF_SSL],
                    CONF_INTERVAL: user_input[CONF_INTERVAL],
                    CONF_NUMBER_OF_TOOLS: user_input[CONF_NUMBER_OF_TOOLS],
                    CONF_BED: user_input[CONF_BED],
                    CONF_LIGHT: user_input[CONF_LIGHT],
                    CONF_MONITORED_CONDITIONS: MONITORED_CONDITIONS,
                    CONF_BASE_URL: "http://{0}:{1}{2}".format(
                        CONF_HOST, CONF_PORT, CONF_API
                    ),
                    CONF_STATUS_PATH: CONF_STATUS_PATH,
                    CONF_GCODE_PATH: CONF_GCODE_PATH,
                },
            )
        return self.async_show_form(
            step_id="user",
            data_schema=_schema_with_defaults(),
            errors=errors,
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        return await self.async_step_user(user_input)
