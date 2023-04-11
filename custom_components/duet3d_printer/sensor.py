"""Support for monitoring Duet3D sensors."""
# TODO: add tool and bed status, need moar sensors!
import logging

import requests

from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

from . import DOMAIN as COMPONENT_DOMAIN, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_ID = "duet3d_notification"
NOTIFICATION_TITLE = "Duet3d sensor setup error"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available Duet3D sensors."""
    if discovery_info is None:
        return

    name = discovery_info["name"]
    base_url = discovery_info["base_url"]
    monitored_conditions = discovery_info["sensors"]
    duet3d_api = hass.data[COMPONENT_DOMAIN][base_url]
    tools = duet3d_api.get_tools()

    if "Temperatures" in monitored_conditions:
        if not tools:
            hass.components.persistent_notification.create(
                "Your printer appears to be offline.<br />"
                "If you do not want to have your printer on <br />"
                " at all times, and you would like to monitor <br /> "
                "temperatures, please add <br />"
                "bed and/or number&#95of&#95tools to your config <br />"
                "and restart.",
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID,
            )

    devices = []
    types = ["current", "active", "standby"]
    bed_types = ["current", "active"]

    for duet3d_type in monitored_conditions:
        endpoint = SENSOR_TYPES[duet3d_type][0]

        if duet3d_type == "Temperatures":
            for tool in tools:
                if tool == "bed":
                    for temp_type in bed_types:
                        new_sensor = Duet3DSensor(
                            duet3d_api,
                            temp_type,
                            temp_type,
                            name,
                            SENSOR_TYPES[duet3d_type][3],
                            SENSOR_TYPES[duet3d_type][0],
                            SENSOR_TYPES[duet3d_type][1],
                            tool,
                        )
                        devices.append(new_sensor)
                else:
                    for temp_type in types:
                        new_sensor = Duet3DSensor(
                            duet3d_api,
                            temp_type,
                            temp_type,
                            name,
                            SENSOR_TYPES[duet3d_type][3],
                            SENSOR_TYPES[duet3d_type][0],
                            SENSOR_TYPES[duet3d_type][1],
                            tool,
                        )
                        devices.append(new_sensor)
        elif endpoint == "array":
            # "Position": [
            #     "array",
            #     "coords.xyz",
            #     "x,y,z",
            #     "mm,mm,mm",
            #     "mdi:format-vertical-align-top,mdi:format-vertical-align-top,mdi:format-vertical-align-top",
            # ],
            # api,
            # condition,
            # sensor_type,
            # sensor_name,
            # unit,
            # endpoint,
            # group,
            # tool=None,
            # icon=None,
            group = SENSOR_TYPES[duet3d_type][1]
            keys = SENSOR_TYPES[duet3d_type][2].split(",")
            units = SENSOR_TYPES[duet3d_type][3].split(",")
            icons = SENSOR_TYPES[duet3d_type][4].split(",")
            index = 0

            for array_item in keys:
                new_sensor = Duet3DSensor(
                    duet3d_api,
                    duet3d_type,
                    array_item,
                    f"{name} {array_item.upper()}",
                    units[index],
                    endpoint,
                    group,
                    f"{index}",
                    icons[index],
                )
                devices.append(new_sensor)
                index += 1

            # new_sensor = Duet3DSensor(
            #     duet3d_api,
            #     duet3d_type,
            #     "y",
            #     f"{name} Y",
            #     SENSOR_TYPES[duet3d_type][3],
            #     SENSOR_TYPES[duet3d_type][0],
            #     SENSOR_TYPES[duet3d_type][1],
            #     "1",
            #     SENSOR_TYPES[duet3d_type][4],
            # )
            # devices.append(new_sensor)

            # new_sensor = Duet3DSensor(
            #     duet3d_api,
            #     duet3d_type,
            #     "z",
            #     f"{name} Z",
            #     SENSOR_TYPES[duet3d_type][3],
            #     SENSOR_TYPES[duet3d_type][0],
            #     SENSOR_TYPES[duet3d_type][1],
            #     "2",
            #     SENSOR_TYPES[duet3d_type][4],
            # )
            # devices.append(new_sensor)
        else:
            new_sensor = Duet3DSensor(
                duet3d_api,
                duet3d_type,
                SENSOR_TYPES[duet3d_type][2],
                name,
                SENSOR_TYPES[duet3d_type][3],
                SENSOR_TYPES[duet3d_type][0],
                SENSOR_TYPES[duet3d_type][1],
                None,
                SENSOR_TYPES[duet3d_type][4],
            )
            devices.append(new_sensor)
    add_entities(devices, True)


class Duet3DSensor(Entity):
    """Representation of an Duet3D sensor."""

    def __init__(
        self,
        api,
        condition,
        sensor_type,
        sensor_name,
        unit,
        endpoint,
        group,
        tool=None,
        icon=None,
    ):
        """Initialize a new Duet3D sensor."""
        self.sensor_name = sensor_name
        if tool is None:
            self._name = f"{sensor_name} {condition}"
        elif endpoint == "array":
            self._name = f"{sensor_name} {condition}"
        else:
            self._name = f"{sensor_name} {condition} tool{tool} temp"
        self.sensor_type = sensor_type
        self.api = api
        self._state = None
        self._unit_of_measurement = unit
        self.api_endpoint = endpoint
        self.api_group = group
        self.api_tool = tool
        self._icon = icon
        self._available = False
        _LOGGER.debug("Created Duet3D sensor %r", self)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        print_status_dict = {
            "S": "Stopped",
            "M": "Simulating",
            "P": "Printing",
            "I": "Idle",
            "C": "Configuring",
            "B": "Busy",
            "D": "Decelerating",
            "R": "Resuming",
            "H": "Halted",
            "F": "Flashing Firmware",
            "T": "Changin Tool",
        }

        sensor_unit = self.unit_of_measurement

        if self._state in print_status_dict:
            self._state = print_status_dict[self._state]

        if sensor_unit in (TEMP_CELSIUS, "%"):
            # API sometimes returns null and not 0
            if self._state is None:
                self._state = 0
            return round(self._state, 2)
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Update state of sensor."""

        try:
            self._state = self.api.update(
                self.sensor_type, self.api_endpoint, self.api_group, self.api_tool
            )
            self._available = True
        except requests.exceptions.ConnectionError:
            # Error calling the api, already logged in api.update()
            self._available = False
            return

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    @property
    def available(self):
        return self._available
