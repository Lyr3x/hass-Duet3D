"""Support for monitoring Duet 3D printers."""
import logging
import time
import asyncio
import requests
import voluptuous as vol
import aiohttp
import async_timeout
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.util import slugify as util_slugify
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
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
    CONF_MONITORED_CONDITIONS,
    CONF_SENSORS,
    CONF_BINARY_SENSORS,
    CONF_SSL,
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
    BINARY_SENSOR_TYPES,
    CONF_LIGHT,
    CONF_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.LIGHT]


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
                        vol.Optional(CONF_LIGHT, default=False): cv.boolean,
                    }
                )
            ],
            has_all_unique_names,
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


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
        coordinator = DuetDataUpdateCoordinator(hass, config_entry, config_entry.data[CONF_INTERVAL])
        coordinator.data["status"] = await coordinator.get_status()
        coordinator.firmware_version = coordinator.get_value_from_json(
            coordinator.data["status"], "boards", "software", "firmwareVersion", None
        )
        coordinator.board_model = coordinator.get_value_from_json(
            coordinator.data["status"], "boards", "software", "model", None
        )
    except requests.exceptions.RequestException as conn_err:
        _LOGGER.error("Error setting up Duet API: %r", conn_err)
        raise ConfigEntryNotReady from conn_err
    hass.data[DOMAIN][config_entry.entry_id] = {"coordinator": coordinator}

    # register Duet3D API services
    async_register_services(hass, coordinator.base_url)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_get_options_flow(config_entry):
    """Return options flow."""
    return Duet3DOptionsFlowHandler(config_entry)


class Duet3DOptionsFlowHandler(OptionsFlow):
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


class DuetDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, interval: int
    ) -> None:
        """Initialize Duet3D API and set headers needed later."""
        super().__init__(
            hass,
            _LOGGER,
            name="duet3d-{config_entry.entry_id}",
            update_interval=timedelta(seconds=interval),
        )
        self.data = {"status": None, "last_read_time": None}
        self.interval = interval
        self.config_entry = config_entry
        self.headers = {"CONTENT_TYPE": "CONTENT_TYPE_JSON"}
        self.status_last_reading = {}
        self.printer_offline = False
        self.status_error_logged = False
        self.number_of_tools = self.config_entry.data[CONF_NUMBER_OF_TOOLS]
        self.bed = self.config_entry.data[CONF_BED]
        self.base_url = "http{0}://{1}:{2}".format(
            "s" if self.config_entry.data[CONF_SSL] else "",
            self.config_entry.data[CONF_HOST],
            self.config_entry.data[CONF_PORT],
        )
        self.status_api_url = "http{0}://{1}:{2}{3}{4}".format(
            "s" if self.config_entry.data[CONF_SSL] else "",
            config_entry.data[CONF_HOST],
            config_entry.data[CONF_PORT],
            CONF_API,
            CONF_STATUS_PATH,
        )
        self.firmware_version = (None,)
        self.board_model = (None,)

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

    async def get_status(self):
        """Send a get request, and return the response as a dict."""
        # Only query the API at most every 30 seconds
        url = self.status_api_url
        _LOGGER.debug("URL: %s", url)
        try:
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=self.headers) as response:
                        response.raise_for_status()
                        data = await response.json()
                        self.status_last_reading = data
                        self.printer_offline = True
                        if self.printer_offline:
                            self.status_error_logged = False
                        return data
        except aiohttp.ClientError as conn_exc:
            log_string = "Failed to update Duet status. " + "  Error: %s" % (conn_exc)
            # Only log the first failure
            log_string = "Endpoint: status " + log_string
            if not self.status_error_logged:
                _LOGGER.error(log_string)
                self.status_error_logged = True
                self.printer_offline = False
            self.printer_offline = False
            return None

    async def _async_update_data(self):
        """Update printer data via API"""
        printer_status = await self.get_status()
        if printer_status is not None:
            return {"status": printer_status, "last_read_time": dt_util.utcnow()}

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
