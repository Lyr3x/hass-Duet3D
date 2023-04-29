"""Config flow for Duet3D Printer integration."""
from homeassistant import config_entries
import logging
from homeassistant.core import callback
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.data_entry_flow import FlowResult
from typing import Any
from homeassistant.helpers.typing import UNDEFINED


from .const import (
    CONF_NUMBER_OF_TOOLS,
    CONF_BED,
    DOMAIN,
    CONF_NAME,
    DEFAULT_NAME,
    CONF_SBC_API,
    CONF_SBC_GCODE_PATH,
    CONF_SBC_STATUS_PATH,
    CONF_BASE_URL,
    CONF_LIGHT,
    CONF_INTERVAL,
    CONF_STANDALONE,
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
    use_standalone=True,
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
            vol.Optional(CONF_STANDALONE, default=use_standalone): bool,
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
                title=f"{user_input[CONF_NAME]} ({user_input[CONF_HOST]})",
                data={
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_SSL: user_input[CONF_SSL],
                    CONF_INTERVAL: user_input[CONF_INTERVAL],
                    CONF_NUMBER_OF_TOOLS: user_input[CONF_NUMBER_OF_TOOLS],
                    CONF_BED: user_input[CONF_BED],
                    CONF_LIGHT: user_input[CONF_LIGHT],
                    CONF_STANDALONE: user_input[CONF_STANDALONE],
                    CONF_BASE_URL: "http://{0}:{1}{2}".format(
                        CONF_HOST, CONF_PORT, CONF_SBC_API
                    ),
                    CONF_SBC_STATUS_PATH: CONF_SBC_STATUS_PATH,
                    CONF_SBC_GCODE_PATH: CONF_SBC_GCODE_PATH,
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

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return Duet3dOptionsFlow(config_entry)


class Duet3dOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Duet3D Printer integration."""

    def __init__(self, config_entry) -> None:
        self.config_entry = config_entry
        self.title: str | None = None

    @callback
    def finish_flow(self) -> FlowResult:
        """Update the ConfigEntry and finish the flow."""
        new_data = self.config_entry.data | self.new_entry_data
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=new_data,
            title=self.title or UNDEFINED,
        )
        return self.async_create_entry(title="", data={})

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        config_data = self.config_entry.data
        config_options = self.config_entry.options
        if user_input is not None:
            self.new_entry_data = {
                CONF_INTERVAL: user_input[CONF_INTERVAL],
                CONF_BED: user_input[CONF_BED],
                CONF_LIGHT: user_input[CONF_LIGHT],
                CONF_STANDALONE: user_input[CONF_STANDALONE],
            }
            return self.finish_flow()
        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_INTERVAL,
                    default=config_options.get(
                        CONF_INTERVAL, config_data.get(CONF_INTERVAL)
                    ),
                ): cv.positive_int,
                vol.Optional(
                    CONF_BED,
                    default=config_data.get(CONF_BED),
                ): bool,
                vol.Optional(
                    CONF_LIGHT,
                    default=config_data.get(CONF_LIGHT),
                ): bool,
                vol.Optional(
                    CONF_STANDALONE,
                    default=config_data.get(CONF_STANDALONE),
                ): bool,
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )
