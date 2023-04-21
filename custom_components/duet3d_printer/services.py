from __future__ import annotations

import asyncio
import logging
import aiohttp
import async_timeout

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    ATTR_GCODE,
    SERVICE_SEND_GCODE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def async_register_services(hass: HomeAssistant) -> None:
    async def send_gcode(call: ServiceCall):
        duet3d_printer_config = hass.data[DOMAIN]
        for key, value in duet3d_printer_config.items():
            if isinstance(value, dict):
                host = value["host"]
                port = value["port"]
        """Send G-code to the printer."""
        url = "http://{}:{}/machine/code".format(host, port)
        headers = {"Content-Type": "text/plain"}

        try:
            async with aiohttp.ClientSession() as session:
                with async_timeout.timeout(10):
                    response = await session.post(
                        url, data=call.data[ATTR_GCODE], headers=headers, ssl=False
                    )
                    response.raise_for_status()
        except (asyncio.TimeoutError, aiohttp.ClientError) as error:
            raise ConnectionError(
                f"Error communicating with printer at {url}"
            ) from error
        else:
            return await response.text()

    if not hass.services.has_service(DOMAIN, SERVICE_SEND_GCODE):
        _LOGGER.debug("Registering service now!")
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_GCODE,
            send_gcode,
            schema=vol.Schema({vol.Required(ATTR_GCODE): str}),
        )
