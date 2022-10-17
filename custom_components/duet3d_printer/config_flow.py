"""Config flow for Duet3D Printer integration."""
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import voluptuous as vol

from .api import IntegrationDuet3DPrinterApiClient
from .const import (
    CONF_HOST,
    DOMAIN
)


class Duet3DPrinterFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Duet3DPrinter."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}

    async def async_step_user(self, info):
        if info is not None:
            self._test_credentials(info[CONF_HOST])

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({vol.Required(CONF_HOST, default=info[CONF_HOST]): str})
        )

    # async def async_step_user(self, user_input=None):
    #     """Handle a flow initialized by the user."""
    #     self._errors = {}

        # Uncomment the next 2 lines if only a single instance of the integration is allowed:
        # if self._async_current_entries():
        #     return self.async_abort(reason="single_instance_allowed")

       

        # if user_input is not None:
        #     valid = await self._test_credentials(
        #         user_input[DOMAIN]
        #     )
        #     if valid:
        #         return self.async_create_entry(
        #             title=user_input[HOST], data=user_input
        #         )
        #     else:
        #         self._errors["base"] = "auth"

        #     return await self._show_config_form(user_input)

        # user_input = {}
        # # Provide defaults for form
        # user_input[DOMAIN] = ""

        # return await self._show_config_form(user_input)

    # @staticmethod
    # @callback
    # def async_get_options_flow(config_entry):
    #     return Duet3DPrinterOptionsFlowHandler(config_entry)

    # async def _show_config_form(self, user_input):  # pylint: disable=unused-argument
    #     """Show the configuration form to edit location data."""
    #     return self.async_show_form(
    #         step_id="user",
    #         data_schema=vol.Schema(
    #             {
    #                 vol.Required(DOMAIN, default=user_input[DOMAIN]): str,
    #             }
    #         ),
    #         errors=self._errors,
    #     )

    async def _test_credentials(self, host):
        """Return true if credentials is valid."""
        return True
        # try:
        #     session = async_create_clientsession(self.hass)
        #     client = IntegrationDuet3DPrinterApiClient(username, password, session)
        #     await client.async_get_data()
        #     return True
        # except Exception:  # pylint: disable=broad-except
        #     pass
        # return False


# class Duet3DPrinterOptionsFlowHandler(config_entries.OptionsFlow):
#     """Duet3DPrinter config flow options handler."""

#     def __init__(self, config_entry):
#         """Initialize HACS options flow."""
#         self.config_entry = config_entry
#         self.options = dict(config_entry.options)

#     async def async_step_init(self, user_input=None):  # pylint: disable=unused-argument
#         """Manage the options."""
#         return await self.async_step_user()

#     async def async_step_user(self, user_input=None):
#         """Handle a flow initialized by the user."""
#         if user_input is not None:
#             self.options.update(user_input)
#             return await self._update_options()

#         return self.async_show_form(
#             step_id="user",
#             data_schema=vol.Schema(
#                 {
#                     vol.Required(x, default=self.options.get(x, True)): bool
#                     for x in sorted(PLATFORMS)
#                 }
#             ),
#         )

#     async def _update_options(self):
#         """Update config entry options."""
#         return self.async_create_entry(
#             title=self.config_entry.data.get(CONF_USERNAME), data=self.options
#         )

# """Config flow for Duet3D Printer integration."""
# from __future__ import annotations

# import logging
# from typing import Any

# import voluptuous as vol

# from homeassistant import config_entries
# from homeassistant.core import HomeAssistant
# from homeassistant.data_entry_flow import FlowResult
# from homeassistant.exceptions import HomeAssistantError

# from .const import DOMAIN

# _LOGGER = logging.getLogger(__name__)

# # TODO adjust the data schema to the data that you need
# STEP_USER_DATA_SCHEMA = vol.Schema({"host": str, "username": str, "password": str})


# class PlaceholderHub:
#     """Placeholder class to make tests pass.

#     TODO Remove this placeholder class and replace with things from your PyPI package.
#     """

#     def __init__(self, host: str) -> None:
#         """Initialize."""
#         self.host = host

#     async def authenticate(self, username: str, password: str) -> bool:
#         """Test if we can authenticate with the host."""
#         return True


# async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
#     """Validate the user input allows us to connect.

#     Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
#     """
#     # TODO validate the data can be used to set up a connection.

#     # If your PyPI package is not built with async, pass your methods
#     # to the executor:
#     # await hass.async_add_executor_job(
#     #     your_validate_func, data["username"], data["password"]
#     # )

#     hub = PlaceholderHub(data["host"])

#     if not await hub.authenticate(data["username"], data["password"]):
#         raise InvalidAuth

#     # If you cannot connect:
#     # throw CannotConnect
#     # If the authentication is wrong:
#     # InvalidAuth

#     # Return info that you want to store in the config entry.
#     return {"title": "Name of the device"}


# class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
#     """Handle a config flow for Duet3D Printer."""

#     VERSION = 1

#     async def async_step_user(
#         self, user_input: dict[str, Any] | None = None
#     ) -> FlowResult:
#         """Handle the initial step."""
#         if user_input is None:
#             return self.async_show_form(
#                 step_id="user", data_schema=STEP_USER_DATA_SCHEMA
#             )

#         errors = {}

#         try:
#             info = await validate_input(self.hass, user_input)
#         except CannotConnect:
#             errors["base"] = "cannot_connect"
#         except InvalidAuth:
#             errors["base"] = "invalid_auth"
#         except Exception:  # pylint: disable=broad-except
#             _LOGGER.exception("Unexpected exception")
#             errors["base"] = "unknown"
#         else:
#             return self.async_create_entry(title=info["title"], data=user_input)

#         return self.async_show_form(
#             step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
#         )


# class CannotConnect(HomeAssistantError):
#     """Error to indicate we cannot connect."""


# class InvalidAuth(HomeAssistantError):
#     """Error to indicate there is invalid auth."""
