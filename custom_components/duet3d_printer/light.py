import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA,
    LightEntity,
    SUPPORT_COLOR,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
import colorsys

from . import DuetDataUpdateCoordinator

from .const import CONF_NAME, ATTR_GCODE, DOMAIN, SERVICE_SEND_GCODE, CONF_LIGHT

_LOGGER = logging.getLogger(__name__)

# Define the validation schema for the platform configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required("name"): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the Duet3D light platform."""
    lightIncluded = config_entry.data[CONF_LIGHT]
    if lightIncluded:
        coordinator: DuetDataUpdateCoordinator = hass.data[DOMAIN][
            config_entry.entry_id
        ]["coordinator"]
        device_id = config_entry.entry_id
        assert device_id is not None
        entities: list[LightEntity] = [
            Duet3DLight(coordinator, "LED", device_id),
        ]
        async_add_entities(entities)


class Duet3DLightBase(CoordinatorEntity[DuetDataUpdateCoordinator], LightEntity):
    """Representation of a light connected to a Duet3D printer."""

    def __init__(
        self, coordinator: DuetDataUpdateCoordinator, light_name: str, device_id: str
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_name = f"{self.device_info['name']} {light_name}"
        self._attr_unique_id = device_id

    @property
    def device_info(self):
        """Device info."""
        return self.coordinator.device_info


class Duet3DLight(Duet3DLightBase):
    def __init__(
        self, coordinator: DuetDataUpdateCoordinator, name: str, device_id: str
    ) -> None:
        super().__init__(coordinator, name, f"{name}-{device_id}")
        self._state = False
        self._brightness = 255
        self._rgb_color = (255, 255, 255)
        self._last_brightness = self._brightness

    @property
    def name(self):
        """Return the name of the light."""
        return self._attr_name

    @property
    def should_poll(self):
        """No polling needed for a Duet3D light."""
        return False

    @property
    def is_on(self):
        """Return the state of the light."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_COLOR

    @property
    def rgb_color(self):
        """Return the RGB color of the light."""
        return self._rgb_color

    def _hs_to_rgb(self, hs_color):
        rgb_color = colorsys.hsv_to_rgb(hs_color[0] / 360, hs_color[1] / 100, 1)
        return tuple(int(round(x * 255)) for x in rgb_color)

    async def async_turn_on(self, **kwargs):
        self._state = True

        # Set the brightness if it was passed in the service call
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            self._last_brightness = self._brightness

        # Set the RGB color if it was passed in the service call
        if "hs_color" in kwargs:
            self._rgb_color = self._hs_to_rgb(kwargs["hs_color"])

        # Use the last brightness value if it was not passed in the service call
        if ATTR_BRIGHTNESS not in kwargs:
            self._brightness = self._last_brightness

        # Build the M150 GCode command
        command = "M150 R{} U{} B{} P{}".format(
            self._rgb_color[0], self._rgb_color[1], self._rgb_color[2], self._brightness
        )

        # Call the send_code service to send the M150 GCode to the Duet3D board
        try:
            await self.hass.services.async_call(
                DOMAIN,
                SERVICE_SEND_GCODE,
                {
                    ATTR_GCODE: command,
                },
            )
        except Exception as e:
            _LOGGER.error("Error calling send_gcode service: %s", e)

        # Update the light state in Home Assistant
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        self._state = False
        # Save the last set brightness before turning the light off
        self._last_brightness = self._brightness
        self._brightness = 0

        # Build the M150 GCode command to turn the light off
        command = "M150 R0 U0 B0 P0"

        # Call the send_code service to send the M150 GCode to the Duet3D board
        try:
            await self.hass.services.async_call(
                DOMAIN,
                SERVICE_SEND_GCODE,
                {
                    ATTR_GCODE: command,
                },
            )
        except Exception as e:
            _LOGGER.error("Error calling send_gcode service: %s", e)

        # Update the light state in Home Assistant
        self.async_schedule_update_ha_state()
