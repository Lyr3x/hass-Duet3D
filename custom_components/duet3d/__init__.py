"""Support for monitoring Duet 3D printers."""
import logging
import requests
import voluptuous as vol
import aiohttp
import asyncio
import async_timeout
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import slugify as util_slugify
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.util.dt as dt_util
from typing import cast
from yarl import URL

from datetime import timedelta


from .services import async_register_services

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    Platform,
    CONF_PASSWORD
)
from .const import (
    CONF_NUMBER_OF_TOOLS,
    CONF_SBC_STATUS_PATH,
    CONF_SBC_API,
    CONF_STANDALONE_API,
    CONF_STANDALONE,
    CONF_BED,
    DOMAIN,
    CONF_INTERVAL,
    SENSOR_TYPES,
    CONF_JSON_HEADER
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.LIGHT, Platform.CAMERA]


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


async def options_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_setup(hass, config):
    """Legacy way to set up Duet3D component from YAML."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up Duet3D component from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    try:
        coordinator = DuetDataUpdateCoordinator(
            hass, config_entry, config_entry.data[CONF_INTERVAL]
        )
        if config_entry.data[CONF_STANDALONE]:
            _LOGGER.info("Using standalone mode")
            try:
                firmwareVersion = await coordinator.get_status(
                    "boards[].firmwareVersion"
                )
                coordinator.firmware_version = firmwareVersion["result"]

                board_model = await coordinator.get_status("boards[].name")
                coordinator.board_model = board_model["result"]
            except (KeyError, TypeError):
                _LOGGER.error("Failed to extract data for sensor")
        else:
            coordinator.data["status"] = await coordinator.get_status()
            coordinator.firmware_version = coordinator.get_value_from_json(
                coordinator.data["status"],
                "boards",
                "software",
                "firmwareVersion",
                None,
            )
            coordinator.board_model = coordinator.get_value_from_json(
                coordinator.data["status"], "boards", "software", "model", None
            )

    except requests.exceptions.RequestException as conn_err:
        _LOGGER.error("Error setting up Duet API: %r", conn_err)
        coordinator.printer_online = False
        raise ConfigEntryNotReady from conn_err
    hass.data[DOMAIN][config_entry.entry_id] = {"coordinator": coordinator}

    # register Duet3D API services
    async_register_services(hass, config_entry)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))
    return True


async def update_listener(hass, entry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok


class DuetDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, interval: int
    ) -> None:
        """Initialize Duet3D API and set headers needed later."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"duet3d-{config_entry.entry_id}",
            update_interval=timedelta(seconds=interval),
        )
        self.data = {"status": None, "last_read_time": None}
        self.interval = interval
        self.config_entry = config_entry
        self.status_last_reading = {}
        self.printer_online = False
        self.status_error_logged = False
        self.number_of_tools = self.config_entry.data[CONF_NUMBER_OF_TOOLS]
        self.bed = self.config_entry.data[CONF_BED]
        self.base_url = "http{0}://{1}:{2}".format(
                "s" if self.config_entry.data[CONF_SSL] else "",
                config_entry.data[CONF_HOST],
                config_entry.data[CONF_PORT]
        )
        
        if self.config_entry.data[CONF_STANDALONE]:
            self.status_api_url = self.base_url+CONF_STANDALONE_API
            #if standalone and has password
            password = config_entry.data[CONF_PASSWORD]
            if(len(password)>0):
                self.identification_path = "/rr_connect?password=" + password
                _LOGGER.warning("connection path: " + self.identification_path)
        else:
            self.status_api_url = "http{0}://{1}:{2}{3}{4}".format(
                "s" if self.config_entry.data[CONF_SSL] else "",
                config_entry.data[CONF_HOST],
                config_entry.data[CONF_PORT],
                CONF_SBC_API,
                CONF_SBC_STATUS_PATH,
            )
        self.firmware_version = (None,)
        self.board_model = (None,)
        self.status_data = {}


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

    async def get_status(self, key=None):
        """Send a get request, and return the response as a dict."""
        
        
        # Only query the API at most every 30 seconds
        if self.config_entry.data[CONF_STANDALONE]:
            url = f"{self.status_api_url}?key={key}"
        else:
            url = self.status_api_url
        _LOGGER.debug("URL: %s", url)

        # send identification if required
        try:
            if (len(self.config_entry.data[CONF_PASSWORD])>0) :
                connection_url = f"{self.base_url}{self.identification_path}"
                async with async_timeout.timeout(10):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            connection_url, headers=CONF_JSON_HEADER
                        ) as response:
                            response.raise_for_status()
        except:
                _LOGGER.error("Could not identify user to 3d printer")

        try:
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=CONF_JSON_HEADER) as response:
                        response.raise_for_status()
                        data = await response.json()
                        self.status_last_reading = data
                        self.printer_online = True
                        if self.printer_online:
                            self.status_error_logged = False
                        return data
        except aiohttp.ClientConnectorError as conn_exc:
            log_string = "Failed to connect to Duet3D board" + "  Error: %s" % (
                conn_exc
            )
            # Only log the first failure
            log_string = "Endpoint: status " + log_string
            if not self.status_error_logged:
                _LOGGER.error(log_string)
                self.status_error_logged = True
            self.printer_online = False
            raise ConfigEntryNotReady(conn_exc) from conn_exc
        except asyncio.TimeoutError as timeout_exc:
            self.printer_online = False
            raise UpdateFailed(timeout_exc) from timeout_exc

    async def _async_update_data(self):
        """Update printer data via API"""
        if self.config_entry.data[CONF_STANDALONE]:
            for sensor_name, sensor_info in SENSOR_TYPES.items():
                json_path = sensor_info["json_path"]
                json_path = json_path.replace("status.", "")
                sensor_data = await self.get_status(json_path)
                if self.status_data is not None and "result" in sensor_data:
                    self.status_data[sensor_name] = sensor_data["result"]
                else:
                    self.status_data[sensor_name] = ""
            return {"status": self.status_data, "last_read_time": dt_util.utcnow()}
        else:
            printer_status = await self.get_status()
            if printer_status is not None:
                return {"status": printer_status, "last_read_time": dt_util.utcnow()}

    def get_sensor_state(self, json_path=None, sensor_name=None):
        if self.config_entry.data[CONF_STANDALONE]:
            if self.data["status"] is not None and sensor_name in self.data["status"]:
                return self.data["status"][sensor_name]
        else:
            return self.get_json_value_by_path(json_path)

    def get_json_value_by_path(self, json_path):
        if json_path is None:
            raise UpdateFailed()
        # convert the JSON response to a dictionary object
        json_data = self.data
        # split the JSON path on period separator and iterate over the path elements
        for path_element in json_path.split("."):
            # if the current path element contains an array index
            if "[" in path_element:
                list_name, index_str = path_element[:-1].split("[")
                # get the value at the specified index in the list
                json_data = json_data[list_name][int(index_str)]
            else:
                # otherwise, access the object property with the current path element
                if path_element not in json_data:
                    return None
                json_data = json_data[path_element]
        return json_data

    @property
    def device_info(self) -> DeviceInfo:
        """Device info."""
        unique_id = cast(str, self.config_entry.unique_id)
        configuration_url = URL.build(
            scheme=self.config_entry.data[CONF_SSL] and "https" or "http",
            host=self.config_entry.data[CONF_HOST],
            port=self.config_entry.data[CONF_PORT],
        )

        return DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Duet3D",
            name=self.config_entry.data[CONF_NAME],
            model=self.board_model,
            sw_version=self.firmware_version,
            configuration_url=str(configuration_url),
        )

    def get_value_from_json(self, json_dict, end_point, sensor_type, group, tool):
        """Return the value for sensor_type from the JSON."""
        if end_point == "boards":
            if group == "firmwareVersion":
                return json_dict[end_point][0]["firmwareVersion"]
            if group == "model":
                return json_dict[end_point][0]["shortName"]
