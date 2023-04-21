"""Support for monitoring Duet 3D printers."""
import logging
import time

import requests
import voluptuous as vol
import aiohttp
import asyncio
import async_timeout
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant
from homeassistant import config_entries
from homeassistant.util import slugify as util_slugify
from .services import async_register_services
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_MONITORED_CONDITIONS,
    CONF_SENSORS,
    CONF_BINARY_SENSORS,
    CONF_SSL,
    TEMP_CELSIUS,
    Platform,
)
from .const import (
    DEFAULT_NAME,
    CONF_NUMBER_OF_TOOLS,
    CONF_STATUS_PATH,
    CONF_API,
    CONF_BED,
    DOMAIN,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


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

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)): vol.All(
            cv.ensure_list, [vol.In(tuple(SENSOR_TYPES))]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

BINARY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_MONITORED_CONDITIONS, default=list(BINARY_SENSOR_TYPES)
        ): vol.All(cv.ensure_list, [vol.In(BINARY_SENSOR_TYPES)]),
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
                        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                        vol.Required(CONF_NUMBER_OF_TOOLS, default=0): cv.positive_int,
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


async def options_update_listener(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_setup(hass, config):
    """Legacy way to set up Duet3D component from YAML."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Set up Duet3D component from a config entry."""
    printers = hass.data.setdefault(DOMAIN, {})
    status_api_url = "http://{0}:{1}{2}{3}".format(
        entry.data[CONF_HOST], entry.data[CONF_PORT], CONF_API, CONF_STATUS_PATH
    )
    number_of_tools = entry.data[CONF_NUMBER_OF_TOOLS]
    bed = entry.data[CONF_BED]
    connect_url = "http://{0}:{1}".format(entry.data[CONF_HOST], entry.data[CONF_PORT])

    try:
        duet_api = Duet3DAPI(connect_url, status_api_url, bed, number_of_tools)
        printers[status_api_url] = duet_api
        await duet_api.get("status")
    except requests.exceptions.RequestException as conn_err:
        _LOGGER.error("Error setting up Duet API: %r", conn_err)

    # register Duet3D API services
    async_register_services(hass, connect_url)
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return True


async def async_get_options_flow(config_entry):
    """Return options flow."""
    return Duet3DOptionsFlowHandler(config_entry)


class Duet3DOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Duet3D options."""

    def __init__(self, config_entry):
        """Initialize Duet3D options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MONITORED_CONDITIONS,
                        default=self.config_entry.options.get(
                            CONF_MONITORED_CONDITIONS,
                            [DEFAULT_SENSOR],
                        ),
                    ): [str],
                }
            ),
        )


class Duet3DAPI:
    def __init__(self, connect_url, status_api_url, bed, number_of_tools):
        """Initialize Duet3D API and set headers needed later."""
        self.connect_url = connect_url
        self.status_api_url = status_api_url
        self.headers = {"CONTENT_TYPE": "CONTENT_TYPE_JSON"}
        self.status_last_reading = [{}, None]
        self.status_available = False
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

    async def get(self, endpoint):
        """Send a get request, and return the response as a dict."""
        # Only query the API at most every 30 seconds
        _LOGGER.debug("passed endpoint: %s", endpoint)
        now = time.time()
        if endpoint == "status":
            last_time = self.status_last_reading[1]
            if last_time is not None:
                if now - last_time < 30.0:
                    return self.status_last_reading[0]
        url = self.status_api_url
        _LOGGER.debug("URL: %s", url)
        try:
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=self.headers) as response:
                        response.raise_for_status()
                        data = await response.json()
                        if endpoint == "status":
                            self.status_last_reading[0] = data
                            self.status_last_reading[1] = time.time()
                            self.status_available = True
                        if self.status_available:
                            self.status_error_logged = False
                        return data
        except aiohttp.ClientError as conn_exc:
            log_string = "Failed to update Duet status. " + "  Error: %s" % (conn_exc)
            # Only log the first failure
            if endpoint == "status":
                log_string = "Endpoint: status " + log_string
                if not self.status_error_logged:
                    _LOGGER.error(log_string)
                    self.status_error_logged = True
                    self.status_available = False
            self.status_available = False
            return None

    async def async_update(self, sensor_type, end_point, group, tool=None):
        """Return the value for sensor_type from the provided endpoint."""
        response = await self.get(end_point)
        if response is not None:
            values_from_json = await get_value_from_json(
                response, end_point, sensor_type, group, tool
            )
            return values_from_json
        return None


async def get_value_from_json(json_dict, end_point, sensor_type, group, tool):
    """Return the value for sensor_type from the JSON."""
    if end_point == "heat":
        if sensor_type == "current":
            if tool == "bed":
                bed_heater = json_dict[end_point][group][0][sensor_type]
                return bed_heater
            else:
                tool_heater = json_dict[end_point][group][1][sensor_type]
                return tool_heater
        elif sensor_type == "active":
            if tool == "bed":
                return json_dict[end_point][group][0][sensor_type]
            else:
                return json_dict[end_point][group][tool][sensor_type]
        return None
    elif end_point == "move":
        axis_json = json_dict[end_point][group]
        axes = ["X", "Y", "Z"]
        positions = [
            axis_json[i]["machinePosition"]
            for i in range(len(axis_json))
            if axis_json[i]["letter"] in axes
        ]
        return str(positions)
    elif end_point == "job" and group == "progress":
        job_total_num_of_layers = json_dict[end_point]["layer"]
        job_printed_num_of_layers = json_dict[end_point]["file"]["numLayers"]
        if (
            job_total_num_of_layers is not None
            and job_printed_num_of_layers is not None
        ):
            progress_percentage = (
                job_total_num_of_layers / job_printed_num_of_layers
            ) * 100
            return progress_percentage
        else:
            return 0
    elif end_point == "job" and group == "timesLeft":
        printTimeLeft = json_dict[end_point][group]["file"]
        if printTimeLeft is not None:
            return round(printTimeLeft / 60.0, 2)
        else:
            return 0
    elif end_point == "job" and group == "duration":
        duration = json_dict[end_point][group]
        if duration is not None:
            return round((json_dict[end_point][group]) / 60, 2)
        else:
            return
    else:
        levels = group.split(".")

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
