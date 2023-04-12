"""Config flow for Duet3D Printer integration."""
from homeassistant import config_entries, core
import logging
from typing import Any, Dict, Optional
from homeassistant.components import websocket_api

from .schema import CONFIG_SCHEMA
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_MONITORED_CONDITIONS,
)

from .const import (
    CONF_NUMBER_OF_TOOLS,
    CONF_BED,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class Duet3dConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Duet3DPrinter."""

    VERSION = 1

    data: Optional[Dict[str, Any]]

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        """Invoked when a user initiates a flow via the user interface."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            _LOGGER.critical("Found user input")
            # validate user input and create config entry
            self.data = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_NAME: user_input.get(CONF_NAME, "Duet3D Printer"),
                CONF_NUMBER_OF_TOOLS: user_input.get(CONF_NUMBER_OF_TOOLS, 1),
                CONF_BED: user_input.get(CONF_BED, False),
                CONF_MONITORED_CONDITIONS: user_input.get(
                    CONF_MONITORED_CONDITIONS, []
                ),
            }
        _LOGGER.critical("No input found")
        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )
