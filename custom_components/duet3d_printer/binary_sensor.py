"""Support for monitoring Duet3D binary sensors."""
import logging

import requests
import aiohttp
from homeassistant.components.binary_sensor import BinarySensorEntity

from . import BINARY_SENSOR_TYPES, DOMAIN as COMPONENT_DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available Duet3D binary sensors."""
    if discovery_info is None:
        return

    name = discovery_info["name"]
    base_url = discovery_info["base_url"]
    monitored_conditions = discovery_info["sensors"]
    duet3d_api = hass.data[COMPONENT_DOMAIN][base_url]

    devices = []
    for duet3d_type in monitored_conditions:
        new_sensor = Duet3DBinarySensor(
            duet3d_api,
            duet3d_type,
            BINARY_SENSOR_TYPES[duet3d_type][2],
            name,
            BINARY_SENSOR_TYPES[duet3d_type][3],
            BINARY_SENSOR_TYPES[duet3d_type][0],
            BINARY_SENSOR_TYPES[duet3d_type][1],
            "flags",
        )
        devices.append(new_sensor)
    add_entities(devices, True)


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
        # return bool(self._state)

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
