"""Support for monitoring Duet3D binary sensors."""
import logging

import requests
import aiohttp
from homeassistant.components.binary_sensor import BinarySensorEntity

from homeassistant.const import (
    CONF_NAME,
)

from .const import DOMAIN, BINARY_SENSOR_TYPES, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the available Duet3D binary sensors."""
    name = config_entry.data[CONF_NAME]
    duet3d_api = list(hass.data[DOMAIN].values())[0]
    current_state_type = SENSOR_TYPES["Current State"]
    printing_type = BINARY_SENSOR_TYPES["Printing"]
    device = Duet3DBinarySensor(
        duet3d_api,
        current_state_type[2],  # key
        printing_type[2],  # name of the binary sensor
        name,
        printing_type[3],  # unit
        printing_type[0],  # group
        printing_type[1],  # endpoint
        "flags",
    )
    async_add_entities([device], True)


class Duet3DBinarySensor(BinarySensorEntity):
    """Representation an Duet3D binary sensor."""

    def __init__(
        self, api, condition, sensor_type, sensor_name, unit, endpoint, group, tool=None
    ):
        """Initialize a new Duet3D sensor."""
        self.sensor_name = sensor_name
        if tool is None:
            self._name = "{} {}".format(sensor_name, condition)
        else:
            self._name = "{} {}".format(sensor_name, condition)
        self.sensor_type = sensor_type
        self.api = api
        self._state = False
        self._unit_of_measurement = unit
        self.api_endpoint = endpoint
        self.api_group = group
        self.api_tool = tool
        _LOGGER.debug("Created Duet3D binary sensor %r", self)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if binary sensor is on."""
        if self._state in {"P", "M"}:
            return 1
        else:
            return 0

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return None

    async def async_update(self):
        """Update state of sensor."""
        try:
            self._state = await self.api.async_update(
                self.sensor_type, self.api_endpoint, self.api_group, self.api_tool
            )
            self._available = True
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Could not update sensor")
            self._available = False
            return
