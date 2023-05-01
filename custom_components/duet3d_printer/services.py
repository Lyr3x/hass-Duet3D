from __future__ import annotations

import asyncio
import logging
import aiohttp
import async_timeout

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
)
from .const import (
    ATTR_GCODE,
    SERVICE_SEND_GCODE,
    DOMAIN,
    CONF_SBC_GCODE_PATH,
    CONF_SBC_API,
    CONF_STANDALONE,
    CONF_STANDALONE_GCODE_PATH,
)

_LOGGER = logging.getLogger(__name__)


def async_register_services(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    async def send_gcode(call: ServiceCall):
        """Send G-code to the printer."""
        if config_entry.data[CONF_STANDALONE]:
            url = "http{0}://{1}:{2}{3}".format(
                "s" if config_entry.data[CONF_SSL] else "",
                config_entry.data[CONF_HOST],
                config_entry.data[CONF_PORT],
                CONF_STANDALONE_GCODE_PATH,
            )
        else:
            url = "http{0}://{1}:{2}{3}{4}".format(
                "s" if config_entry.data[CONF_SSL] else "",
                config_entry.data[CONF_HOST],
                config_entry.data[CONF_PORT],
                CONF_SBC_API,
                CONF_SBC_GCODE_PATH,
            )
        headers = {"Content-Type": "text/plain"}

        try:
            async with aiohttp.ClientSession() as session:
                with async_timeout.timeout(10):
                    if config_entry.data[CONF_STANDALONE]:
                        response = await session.get(
                            url, params=call.data[ATTR_GCODE], headers=headers, ssl=False
                        )
                    else:
                        response = await session.post(
                            url, data=call.data[ATTR_GCODE], headers=headers, ssl=False
                        )
                    response.raise_for_status()
                    if response.status == 200:
                        return await response.text()
        except (asyncio.TimeoutError, aiohttp.ClientError) as error:
            raise ConnectionError(
                f"Error communicating with printer at {url}"
            ) from error

    if not hass.services.has_service(DOMAIN, SERVICE_SEND_GCODE):
        _LOGGER.debug("Registering service now!")
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_GCODE,
            send_gcode,
            schema=vol.Schema({vol.Required(ATTR_GCODE): str}),
        )
