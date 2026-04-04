from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry

from .const import (
    ATTR_GCODE,
    SERVICE_SEND_GCODE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def async_register_services(hass: HomeAssistant, config_entry: ConfigEntry, coordinator) -> None:
    async def send_gcode(call: ServiceCall):
        """Send G-code to the printer."""
        try:
            await coordinator.send_gcode(call.data[ATTR_GCODE])
        except Exception as error:
            raise ConnectionError(
                f"Error communicating with printer: {error}"
            ) from error

    if not hass.services.has_service(DOMAIN, SERVICE_SEND_GCODE):
        _LOGGER.debug("Registering service now!")
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_GCODE,
            send_gcode,
            schema=vol.Schema({vol.Required(ATTR_GCODE): str}),
        )
