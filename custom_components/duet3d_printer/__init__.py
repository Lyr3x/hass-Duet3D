"""Support for monitoring Duet 3D printers."""
import logging
import time

import requests
import voluptuous as vol
from aiohttp.hdrs import CONTENT_TYPE

# from homeassistant.components.discovery import SERVICE_OCTOPRINT
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONTENT_TYPE_JSON,
    CONF_NAME,
    CONF_PASSWORD,
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
    # "Printing Error": ['printer', 'state', 'error', None]
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
    "Temperatures": ["temps", "temperature", "*", TEMP_CELSIUS],
    "Current State": ["job", "status", "text", None, "mdi:printer-3d"],
    "Job Percentage": ["job", "fractionPrinted", "completion", "%", "mdi:file-percent"],
    "Time Remaining": ["job", "timesLeft", "file", "seconds", "mdi:clock-end"],
    "Time Elapsed": ["job", "printDuration", "printTime", "seconds", "mdi:clock-start"],
    "Position": [
        "array",
        "coords.xyz",
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
                        # vol.Required(CONF_API_KEY): cv.string,
                        vol.Required(CONF_HOST): cv.string,
                        vol.Required(CONF_PASSWORD) : cv.string,
                        vol.Optional(CONF_SSL, default=False): cv.boolean,
                        vol.Optional(CONF_PORT, default=80): cv.port,
                        # type 2, extended infos, type 3, print status infos
                        vol.Optional(
                            CONF_PATH, default="/rr_status?type=3"
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
    """Set up the OctoPrint component."""
    printers = hass.data[DOMAIN] = {}
    success = False

    # def device_discovered(service, info):
    #     """Gets called when a Duet3D device has been discovered."""
    #     _LOGGER.debug("Found a Duet3D device: %s", info)
    #
    # discovery.listen(hass, SERVICE_OCTOPRINT, device_discovered)

    if DOMAIN not in config:
        # Skip the setup if there is no configuration present
        return True

    for printer in config[DOMAIN]:
        name = printer[CONF_NAME]
        ssl = "s" if printer[CONF_SSL] else ""
        api_url = "http{}://{}:{}{}".format(
            ssl, printer[CONF_HOST], printer[CONF_PORT], printer[CONF_PATH]
        )
        api_key = 0
        number_of_tools = printer[CONF_NUMBER_OF_TOOLS]
        bed = printer[CONF_BED]
        connect_path = "/rr_connect?password=" + printer[CONF_PASSWORD]
        connect_url = "http{0}://{1}:{2}{3}".format(ssl, printer[CONF_HOST], printer[CONF_PORT], connect_path)
        try:
            octoprint_api = Duet3dAPI(connect_url, api_url, api_key, bed, number_of_tools)
            printers[api_url] = octoprint_api
            octoprint_api.get("printer")
            octoprint_api.get("job")
        except requests.exceptions.RequestException as conn_err:
            _LOGGER.error("Error setting up OctoPrint API: %r", conn_err)
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
    """Simple JSON wrapper for OctoPrint's API."""

    def __init__(self, connect_url, api_url, key, bed, number_of_tools):
        """Initialize OctoPrint API and set headers needed later."""
        self.connect_url = connect_url
        self.api_url = api_url
        self.headers = {
            "CONTENT_TYPE": "CONTENT_TYPE_JSON",
            #'X-Api-Key': key,
        }
        self.printer_last_reading = [{}, None]
        self.job_last_reading = [{}, None]
        self.job_available = False
        self.printer_available = False
        self.available = False
        self.printer_error_logged = False
        self.job_error_logged = False
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
            temps = self.printer_last_reading[0].get("temperature")
            if temps is not None:
                tools = temps.keys()
        return tools

    def get(self, endpoint):
        """Send a get request, and return the response as a dict."""
        # Only query the API at most every 30 seconds
        now = time.time()
        if endpoint == "job":
            last_time = self.job_last_reading[1]
            if last_time is not None:
                if now - last_time < 30.0:
                    return self.job_last_reading[0]
        elif endpoint == "printer":
            last_time = self.printer_last_reading[1]
            if last_time is not None:
                if now - last_time < 30.0:
                    return self.printer_last_reading[0]

        url = self.api_url  # + endpoint
        try:
            connect = requests.get(self.connect_url)
            response = requests.get(url, headers=self.headers, timeout=9)
            response.raise_for_status()
            if endpoint == "job":
                self.job_last_reading[0] = response.json()
                self.job_last_reading[1] = time.time()
                self.job_available = True
            elif endpoint == "printer":
                self.printer_last_reading[0] = response.json()
                self.printer_last_reading[1] = time.time()
                self.printer_available = True
            self.available = self.printer_available and self.job_available
            if self.available:
                self.job_error_logged = False
                self.printer_error_logged = False
            return response.json()
        except Exception as conn_exc:  # pylint: disable=broad-except
            log_string = "Failed to update OctoPrint status. " + "  Error: %s" % (
                conn_exc
            )
            # Only log the first failure
            if endpoint == "job":
                log_string = "Endpoint: job " + log_string
                if not self.job_error_logged:
                    _LOGGER.error(log_string)
                    self.job_error_logged = True
                    self.job_available = False
            elif endpoint == "printer":
                log_string = "Endpoint: printer " + log_string
                if not self.printer_error_logged:
                    _LOGGER.error(log_string)
                    self.printer_error_logged = True
                    self.printer_available = False
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
    if end_point == "temps":
        if sensor_type == "current":
            if tool == "bed":
                return json_dict[end_point][sensor_type][0]
            else:
                return json_dict[end_point][sensor_type][tool]
        elif sensor_type == "active":
            if tool == "bed":
                return json_dict[end_point]["bed"][sensor_type]
            else:
                return json_dict[end_point]["tools"][sensor_type][tool - 1][tool - 1]
    # elif end_point == "array":

        # if "coords" not in json_dict:
        #     return 0
        # return json_dict["coords"][group][int(tool)]
    else:
        levels = group.split(".")
        data = json_dict

        if group == "timesLeft":
            return json_dict[group]["file"]

        for level in levels:
            _LOGGER.debug(
                "Updating API Duet3D sensor: get_value_from_json, array, %s, %r",
                level,
                data,
            )
            if level not in data:
                return 0
            data = data[level]

        if end_point == "array":
            return data[int(tool)]
        else:
            return data

        return None
