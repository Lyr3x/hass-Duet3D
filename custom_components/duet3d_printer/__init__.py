"""Support for monitoring Duet 3D printers."""
import logging
import time

import requests
import voluptuous as vol
from aiohttp.hdrs import CONTENT_TYPE

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    TEMP_CELSIUS,
    CONF_MONITORED_CONDITIONS,
    CONF_SENSORS,
    CONF_BINARY_SENSORS,
)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.util import slugify as util_slugify

_LOGGER = logging.getLogger(__name__)

CONF_BED = "bed"
CONF_NUMBER_OF_TOOLS = "number_of_tools"

DEFAULT_NAME = "Duet3D Printer"
DOMAIN = "duet3d_printer"


def has_all_unique_names(value):
    """Validate that printers have an unique name."""
    names = [util_slugify(printer["name"]) for printer in value]
    vol.Schema(vol.Unique())(names)
    return value


def ensure_valid_path(value):
    """Validate the path, ensuring it starts and ends with a /."""
    vol.Schema(cv.string)(value)
    if value[0] != "/":
        value = "/" + value
    if value[-1] != "/":
        value += "/"
    return value


BINARY_SENSOR_TYPES = {
    # API Endpoint, Group, Key, unit
    "Printing": ["job", "status", "printing", None],
}

BINARY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_MONITORED_CONDITIONS, default=list(BINARY_SENSOR_TYPES)
        ): vol.All(cv.ensure_list, [vol.In(BINARY_SENSOR_TYPES)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

SENSOR_TYPES = {
    # API Endpoint, Group, Key, unit, icon
    # Group, subgroup, key, unit, icon
    "Temperatures": [
        "heat",
        "heaters",
        "*",
        TEMP_CELSIUS,
        "mdi:thermometer",
    ],
    "Current State": [
        "state",
        "state.status",
        "status",
        None,
        "mdi:printer-3d",
    ],
    "Time Remaining": [
        "job",
        "timesLeft.file",
        "file",
        "seconds",
        "mdi:clock-end",
    ],
    "Time Elapsed": [
        "job",
        "printDuration",
        "printTime",
        "seconds",
        "mdi:clock-start",
    ],
    "Position": [
        "move",
        "axes",
        "x,y,z",
        "mm,mm,mm",
        "mdi:axis-x-arrow,mdi:axis-y-arrow,mdi:axis-z-arrow",
    ],
}


SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): cv.string,
                        vol.Optional(CONF_SSL, default=False): cv.boolean,
                        vol.Optional(CONF_PORT, default=80): cv.port,
                        vol.Optional(
                            CONF_PATH, default="/machine/status"
                        ): ensure_valid_path,
                        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                        vol.Optional(CONF_NUMBER_OF_TOOLS, default=0): cv.positive_int,
                        vol.Optional(CONF_BED, default=False): cv.boolean,
                        vol.Optional(CONF_SENSORS, default={}): SENSOR_SCHEMA,
                        vol.Optional(
                            CONF_BINARY_SENSORS, default={}
                        ): BINARY_SENSOR_SCHEMA,
                    }
                )
            ],
            has_all_unique_names,
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the Duet component."""
    printers = hass.data[DOMAIN] = {}
    success = False


    if DOMAIN not in config:
        # Skip the setup if there is no configuration present
        return True

    for printer in config[DOMAIN]:
        name = printer[CONF_NAME]
        ssl = "s" if printer[CONF_SSL] else ""
        api_url = "http{}://{}:{}{}".format(
            ssl, printer[CONF_HOST], printer[CONF_PORT], printer[CONF_PATH]
        )
        number_of_tools = printer[CONF_NUMBER_OF_TOOLS]
        bed = printer[CONF_BED]
        connect_url = "http{0}://{1}:{2}".format(ssl, printer[CONF_HOST], printer[CONF_PORT])
        try:
            duet_api = Duet3dAPI(connect_url, api_url, bed, number_of_tools)
            printers[api_url] = duet_api
            duet_api.get("status")
        except requests.exceptions.RequestException as conn_err:
            _LOGGER.error("Error setting up Duet API: %r", conn_err)
            continue

        sensors = printer[CONF_SENSORS][CONF_MONITORED_CONDITIONS]
        load_platform(
            hass,
            "sensor",
            DOMAIN,
            {"name": name, "base_url": api_url, "sensors": sensors},
            config,
        )
        b_sensors = printer[CONF_BINARY_SENSORS][CONF_MONITORED_CONDITIONS]
        load_platform(
            hass,
            "binary_sensor",
            DOMAIN,
            {"name": name, "base_url": api_url, "sensors": b_sensors},
            config,
        )
        success = True

    return success


class Duet3dAPI:
    """Simple JSON wrapper for Duet3D's API."""

    def __init__(self, connect_url, api_url, bed, number_of_tools):
        """Initialize Duet3D API and set headers needed later."""
        self.connect_url = connect_url
        self.api_url = api_url
        self.headers = {
            "CONTENT_TYPE": "CONTENT_TYPE_JSON"
        }
        self.status_last_reading = [{}, None]
        self.available = False
        self.status_error_logged = False
        self.bed = bed
        self.number_of_tools = number_of_tools

    def get_tools(self):
        """Get the list of tools that temperature is monitored on."""
        tools = []
        if self.number_of_tools > 0:
            # tools start at 1 bed is 0
            for tool_number in range(1, self.number_of_tools + 1):
                tools.append(tool_number)  #'tool' + str(tool_number))
        if self.bed:
            tools.append("bed")
        if not self.bed and self.number_of_tools == 0:
            temps = self.status_last_reading[0].get("temperature")
            if temps is not None:
                tools = temps.keys()
        return tools

    def get(self, endpoint):
        """Send a get request, and return the response as a dict."""
        # Only query the API at most every 30 seconds
        _LOGGER.debug("passed endpoint: %s", endpoint)
        now = time.time()
        if endpoint == "status":
            last_time = self.status_last_reading[1]
            if last_time is not None:
                if now - last_time < 30.0:
                    return self.status_last_reading[0]
        url = self.api_url
        _LOGGER.debug("URL: %s", url)
        try:
            # connect = requests.get(self.connect_url) # We need to implement that later to use session keys
            response = requests.get(url, headers=self.headers, timeout=9)
            response.raise_for_status()
            data = response.json()
            if endpoint == "status":
                self.status_last_reading[0] = data
                self.status_last_reading[1] = time.time()
                self.status_available = True
            self.available = self.status_available
            if self.available:
                self.status_error_logged = False
            return data
        except Exception as conn_exc:  # pylint: disable=broad-except
            log_string = "Failed to update Duet status. " + "  Error: %s" % (
                conn_exc
            )
            # Only log the first failure
            if endpoint == "status":
                log_string = "Endpoint: status " + log_string
                if not self.status_error_logged:
                    _LOGGER.error(log_string)
                    self.status_error_logged = True
                    self.status_available = False
            self.available = False
            return None

    def update(self, sensor_type, end_point, group, tool=None):
        """Return the value for sensor_type from the provided endpoint."""
        _LOGGER.debug(
            "Updating API Duet3D sensor %r, Type: %s, End Point: %s, Group: %s, Tool: %s",
            self,
            sensor_type,
            end_point,
            group,
            tool,
        )
        response = self.get(end_point)
        if response is not None:
            return get_value_from_json(response, end_point, sensor_type, group, tool)
        return response


def get_value_from_json(json_dict, end_point, sensor_type, group, tool):
    """Return the value for sensor_type from the JSON."""
    if end_point == "heat":
        if sensor_type == "current":
            if tool == "bed":
                bed_heater = json_dict[end_point][group][0][sensor_type]
                return bed_heater
            else:
                tool_heater = json_dict[end_point][group][1][sensor_type]
                _LOGGER.debug(tool_heater)
                return tool_heater
        elif sensor_type == "active":
            if tool == "bed":
                return json_dict[end_point][group][0][sensor_type]
            else:
                return json_dict[end_point][group][tool][sensor_type]
        return None
    elif end_point == "move":
        axis_json =json_dict[end_point][group]
        axes = ["X", "Y", "Z"]
        positions = [axis_json[i]["machinePosition"] for i in range(len(axis_json)) if axis_json[i]["letter"] in axes]
        _LOGGER.debug(positions)
        return str(positions)
    else:
        levels = group.split(".")

        if group == "timesLeft":
            return json_dict[group]["file"]

        for level in levels:
            _LOGGER.debug(
                "Updating API Duet3D sensor: get_value_from_json, array, %s, %r",
                level,
                json_dict,
            )
            if level not in json_dict:
                return 0
            json_dict = json_dict[level]

        if end_point == "array":
            return json_dict[int(tool)]
        else:
            return json_dict
