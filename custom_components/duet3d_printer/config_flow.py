"""Config flow for Duet3D Printer integration."""
from homeassistant import config_entries
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
)

from .const import (
    CONF_NAME,
    CONF_NUMBER_OF_TOOLS,
    CONF_BED,
    CONF_MONITORED_CONDITIONS,
    DOMAIN
)

class Duet3dAPIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Duet3DPrinter."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}
        if user_input is not None:
            # validate user input and create config entry
            data = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_NAME: user_input.get(CONF_NAME, "Duet3D Printer"),
                CONF_NUMBER_OF_TOOLS: user_input.get(CONF_NUMBER_OF_TOOLS, 1),
                CONF_BED: user_input.get(CONF_BED, False),
                CONF_MONITORED_CONDITIONS: user_input.get(
                    CONF_MONITORED_CONDITIONS, []
                ),
            }
            try:
                await self._test_credentials(data[CONF_HOST])
                return self.async_create_entry(title=data[CONF_NAME], data=data)
            except Exception as e:
                self._errors[CONF_HOST] = "cannot_connect"
        # show user form to enter configuration options
        return self
