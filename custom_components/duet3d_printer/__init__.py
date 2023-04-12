"""Support for monitoring Duet 3D printers."""
import logging
import time

import requests
import voluptuous as vol

from .schema import CONFIG_SCHEMA, SENSOR_TYPES, BINARY_SENSOR_TYPES

from homeassistant.const import (
    CONF_HOST,
    CONF_PATH,
    CONF_PORT,
    CONF_SENSORS,
    CONF_BINARY_SENSORS,
    CONF_MONITORED_CONDITIONS,
    CONF_SSL,
    Platform,
)

from .const import (
    CONF_NAME,
    CONF_NUMBER_OF_TOOLS,
    CONF_BED,
    DOMAIN,
)

# from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Duet3D from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)
    # Registers update listener to update config entry when options are updated.
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    # Store a reference to the unsubscribe function to cleanup if an entry is unloaded.
    hass_data["unsub_options_update_listener"] = unsub_options_update_listener
    hass.data[DOMAIN][entry.entry_id] = hass_data
    _LOGGER.critical(entry)
    # Forward the setup to the sensor platform.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True


async def options_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[hass.config_entries.async_forward_entry_unload(entry, "sensor")]
        )
    )
    # Remove options_update_listener.
    hass.data[DOMAIN][entry.entry_id]["unsub_options_update_listener"]()

    # Remove config entry from domain.
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def setup(hass, config) -> bool:
    """Set up the Duet3D component from yaml configuration."""
    printers = hass.data.setdefault(DOMAIN, {})
    success = False

    if DOMAIN not in config:
        # Skip the setup if there is no configuration present
        _LOGGER.error("Domain is not in config. Skipping setup of integration")
        return True

    setting = config[DOMAIN]
    for setting in config[DOMAIN]:
        name = setting[CONF_NAME]
        ssl = "s" if setting.get(CONF_SSL, False) else ""
        api_url = "http{}://{}:{}{}".format(
            ssl, setting[CONF_HOST], setting[CONF_PORT], setting[CONF_PATH]
        )
        number_of_tools = setting[CONF_NUMBER_OF_TOOLS]
        bed = setting[CONF_BED]
        connect_url = "http{0}://{1}:{2}".format(
            ssl, setting[CONF_HOST], setting[CONF_PORT]
        )
        try:
            duet_api = Duet3dAPI(connect_url, api_url, bed, number_of_tools)
            printers[api_url] = duet_api
            duet_api.get("status")
        except requests.exceptions.RequestException as conn_err:
            _LOGGER.error("Error setting up Duet API: %r", conn_err)

        sensors = setting[CONF_SENSORS][CONF_MONITORED_CONDITIONS]
        load_platform(
            hass,
            "sensor",
            DOMAIN,
            {"name": name, "base_url": api_url, "sensors": sensors},
            config,
        )
        b_sensors = setting[CONF_BINARY_SENSORS][CONF_MONITORED_CONDITIONS]
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
        self.headers = {"CONTENT_TYPE": "CONTENT_TYPE_JSON"}
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
            log_string = "Failed to update Duet status. " + "  Error: %s" % (conn_exc)
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
        axis_json = json_dict[end_point][group]
        axes = ["X", "Y", "Z"]
        positions = [
            axis_json[i]["machinePosition"]
            for i in range(len(axis_json))
            if axis_json[i]["letter"] in axes
        ]
        _LOGGER.debug(positions)
        return str(positions)
    elif end_point == "job" and group == "duration":
        job_duration = json_dict[end_point][group]
        job_file_total_print_time = json_dict[end_point]["file"]["printTime"]
        progress_percentage = job_duration / job_file_total_print_time * 100
        return progress_percentage
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
