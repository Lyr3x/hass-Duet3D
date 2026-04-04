"""Support for monitoring Duet 3D printers."""
import logging
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
    CONF_SBC_GCODE_PATH,
    CONF_STANDALONE_API,
    CONF_STANDALONE_GCODE_PATH,
    CONF_STANDALONE,
    CONF_BED,
    DOMAIN,
    CONF_INTERVAL,
    SENSOR_TYPES,
    CONF_JSON_HEADER,
    CONF_TEXT_PLAIN_HEADER,
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

    coordinator = DuetDataUpdateCoordinator(
        hass, config_entry, config_entry.data[CONF_INTERVAL]
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await coordinator.async_close_session()
        raise

    # Extract firmware and board info from the first successful data fetch
    try:
        if config_entry.data[CONF_STANDALONE]:
            _LOGGER.info("Using standalone mode")
            fw_data = await coordinator.get_status("boards[].firmwareVersion")
            coordinator.firmware_version = fw_data.get("result")
            board_data = await coordinator.get_status("boards[].name")
            coordinator.board_model = board_data.get("result")
        else:
            status = coordinator.data.get("status")
            if status:
                coordinator.firmware_version = coordinator.get_value_from_json(
                    status, "boards", "software", "firmwareVersion", None
                )
                coordinator.board_model = coordinator.get_value_from_json(
                    status, "boards", "software", "model", None
                )
    except (KeyError, TypeError):
        _LOGGER.error("Failed to extract firmware/board data")

    hass.data[DOMAIN][config_entry.entry_id] = {"coordinator": coordinator}

    # register Duet3D API services (pass coordinator for auth)
    async_register_services(hass, config_entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))
    return True


async def update_listener(hass, entry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await coordinator.async_close_session()
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
            config_entry.data[CONF_PORT],
        )

        if self.config_entry.data[CONF_STANDALONE]:
            self.status_api_url = self.base_url + CONF_STANDALONE_API
        else:
            self.status_api_url = "{0}{1}{2}".format(
                self.base_url,
                CONF_SBC_API,
                CONF_SBC_STATUS_PATH,
            )

        self._password = config_entry.data.get(CONF_PASSWORD, "")
        self._session: aiohttp.ClientSession | None = None
        self._authenticated = False
        self.firmware_version = None
        self.board_model = None
        self.status_data = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create a persistent aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._authenticated = False
        return self._session

    async def _ensure_authenticated(self):
        """Authenticate with the printer if using standalone mode with a password."""
        if not self.config_entry.data[CONF_STANDALONE]:
            return
        if not self._password:
            return
        if self._authenticated:
            return

        session = await self._get_session()
        connect_url = f"{self.base_url}/rr_connect?password={self._password}"
        try:
            async with async_timeout.timeout(10):
                async with session.get(connect_url, headers=CONF_JSON_HEADER) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    if data.get("err", 1) == 0:
                        self._authenticated = True
                        _LOGGER.debug("Authenticated with printer")
                    else:
                        _LOGGER.error(
                            "Authentication failed (err=%s)", data.get("err")
                        )
        except Exception as exc:
            _LOGGER.error("Could not authenticate with printer: %s", exc)
            self._authenticated = False

    async def async_close_session(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            self._authenticated = False

    def get_tools(self):
        """Get the list of tools that temperature is monitored on."""
        tools = []
        if self.number_of_tools > 0:
            for tool_number in range(1, self.number_of_tools + 1):
                tools.append(tool_number)
        if self.bed:
            tools.append("bed")
        if not self.bed and self.number_of_tools == 0:
            temps = self.status_last_reading[0].get("temperature")
            if temps is not None:
                tools = temps.keys()
        return tools

    async def get_status(self, key=None):
        """Send a get request, and return the response as a dict."""
        if self.config_entry.data[CONF_STANDALONE]:
            url = f"{self.status_api_url}?key={key}"
        else:
            url = self.status_api_url
        _LOGGER.debug("URL: %s", url)

        await self._ensure_authenticated()
        session = await self._get_session()

        try:
            async with async_timeout.timeout(10):
                async with session.get(url, headers=CONF_JSON_HEADER) as response:
                    if response.status == 401:
                        # Session expired, re-authenticate and retry once
                        _LOGGER.debug("Session expired, re-authenticating")
                        self._authenticated = False
                        await self._ensure_authenticated()
                        async with session.get(
                            url, headers=CONF_JSON_HEADER
                        ) as retry_resp:
                            retry_resp.raise_for_status()
                            data = await retry_resp.json()
                    else:
                        response.raise_for_status()
                        data = await response.json()

                    self.status_last_reading = data
                    self.printer_online = True
                    self.status_error_logged = False
                    return data
        except aiohttp.ClientConnectorError as conn_exc:
            if not self.status_error_logged:
                _LOGGER.error("Failed to connect to Duet3D board: %s", conn_exc)
                self.status_error_logged = True
            self.printer_online = False
            raise ConfigEntryNotReady(conn_exc) from conn_exc
        except asyncio.TimeoutError as timeout_exc:
            self.printer_online = False
            raise UpdateFailed(timeout_exc) from timeout_exc

    async def send_gcode(self, gcode: str) -> str | None:
        """Send G-code to the printer (used by service handler)."""
        await self._ensure_authenticated()
        session = await self._get_session()

        if self.config_entry.data[CONF_STANDALONE]:
            url = f"{self.base_url}{CONF_STANDALONE_GCODE_PATH}"
            params = {"gcode": gcode}
            async with async_timeout.timeout(10):
                async with session.get(
                    url, params=params, headers=CONF_TEXT_PLAIN_HEADER
                ) as response:
                    if response.status == 401:
                        self._authenticated = False
                        await self._ensure_authenticated()
                        async with session.get(
                            url, params=params, headers=CONF_TEXT_PLAIN_HEADER
                        ) as retry_resp:
                            retry_resp.raise_for_status()
                            return await retry_resp.text()
                    response.raise_for_status()
                    return await response.text()
        else:
            url = f"{self.base_url}{CONF_SBC_API}{CONF_SBC_GCODE_PATH}"
            async with async_timeout.timeout(10):
                async with session.post(
                    url, data=gcode, headers=CONF_TEXT_PLAIN_HEADER
                ) as response:
                    response.raise_for_status()
                    return await response.text()

    async def _async_update_data(self):
        """Update printer data via API."""
        if self.config_entry.data[CONF_STANDALONE]:
            for sensor_name, sensor_info in SENSOR_TYPES.items():
                json_path = sensor_info["json_path"]
                json_path = json_path.replace("status.", "")
                sensor_data = await self.get_status(json_path)
                if sensor_data is not None and "result" in sensor_data:
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
        json_data = self.data
        for path_element in json_path.split("."):
            if "[" in path_element:
                list_name, index_str = path_element[:-1].split("[")
                json_data = json_data[list_name][int(index_str)]
            else:
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
