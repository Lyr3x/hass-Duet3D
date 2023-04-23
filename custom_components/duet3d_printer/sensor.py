"""Support for monitoring Duet3D sensors."""
# TODO: add tool and bed status, need moar sensors!
import logging

import requests
import aiohttp
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry

from . import DuetDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_ID = "duet3d_notification"
NOTIFICATION_TITLE = "Duet3d sensor setup error"

from homeassistant.const import (
    CONF_NAME,
)
from .const import DOMAIN, SENSOR_TYPES, CONF_MONITORED_CONDITIONS, PRINTER_STATUS_DICT


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the available Duet3D sensors."""
    name = config_entry.data[CONF_NAME]
    monitored_conditions = config_entry.data[CONF_MONITORED_CONDITIONS]
    coordinator: DuetDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]
    tools = coordinator.get_tools()
    device_id = config_entry.entry_id
    assert device_id is not None

    if "Temperatures" in monitored_conditions:
        if not tools:
            hass.components.persistent_notification.async_create(
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

    for condition in monitored_conditions:
        endpoint = SENSOR_TYPES[condition][0]

        if condition == "Temperatures":
            for tool in tools:
                if tool == "bed":
                    for temp_type in bed_types:
                        new_sensor = Duet3DSensor(
                            coordinator,
                            device_id,
                            condition,
                            name,
                            temp_type,
                            f"{name} Tool {tool} {temp_type}",
                            SENSOR_TYPES[condition][3],
                            SENSOR_TYPES[condition][0],
                            SENSOR_TYPES[condition][1],
                            tool,
                        )
                        devices.append(new_sensor)
                else:
                    for temp_type in types:
                        new_sensor = Duet3DSensor(
                            coordinator,
                            device_id,
                            condition,
                            name,
                            temp_type,
                            f"{name} Tool {tool} {temp_type}",
                            SENSOR_TYPES[condition][3],
                            SENSOR_TYPES[condition][0],
                            SENSOR_TYPES[condition][1],
                            tool,
                        )
                        devices.append(new_sensor)
        elif endpoint == "array":
            group = SENSOR_TYPES[condition][1]
            keys = SENSOR_TYPES[condition][2].split(",")
            units = SENSOR_TYPES[condition][3].split(",")
            icons = SENSOR_TYPES[condition][4].split(",")
            index = 0

            for array_item in keys:
                new_sensor = Duet3DSensor(
                    coordinator,
                    device_id,
                    condition,
                    name,
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

        else:
            new_sensor = Duet3DSensor(
                coordinator,
                device_id,
                condition,
                name,
                SENSOR_TYPES[condition][2],
                f"{name} {condition}",
                SENSOR_TYPES[condition][3],
                SENSOR_TYPES[condition][0],
                SENSOR_TYPES[condition][1],
                None,
                SENSOR_TYPES[condition][4],
            )
            devices.append(new_sensor)
    async_add_entities(devices, True)


class DuetPrintSensorBase(CoordinatorEntity[DuetDataUpdateCoordinator], Entity):
    """Representation of an OctoPrint sensor."""

    def __init__(
        self,
        coordinator: DuetDataUpdateCoordinator,
        sensor_type: str,
        name: str,
        sensor_name: str,
        device_id: str,
    ) -> None:
        """Initialize a new Duet3D sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_name = f"{name} {sensor_type}"
        self._attr_unique_id = f"{sensor_name}-{device_id}"

    @property
    def device_info(self):
        """Device info."""
        return self.coordinator.device_info


class Duet3DSensor(DuetPrintSensorBase):
    """Representation of an Duet3D sensor."""

    def __init__(
        self,
        coordinator: DuetDataUpdateCoordinator,
        device_id: str,
        name: str,
        condition,
        sensor_type,
        sensor_name,
        unit,
        endpoint,
        group,
        tool=None,
        icon=None,
    ) -> None:
        """Initialize a new Duet3D sensor."""
        super().__init__(
            coordinator, sensor_type, name, f"{sensor_name}-{condition}", device_id
        )
        self.sensor_name = sensor_name
        self.sensor_type = sensor_type
        self.coordinator = coordinator
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
        return self.sensor_name

    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.debug(self._state)
        sensor_unit = self.unit_of_measurement
        if self._state in PRINTER_STATUS_DICT:
            self._state = PRINTER_STATUS_DICT[self._state]

        if sensor_unit in (TEMP_CELSIUS, "%"):
            # API sometimes returns null and not 0
            if self._state is None:
                self._state = 0
            return round(float(self._state), 2)
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    async def async_update(self):
        """Update state of sensor."""
        try:
            data = self._state = await self.coordinator._async_update_data()
            if data is not None:
                self._available = True
                self._state = await self.coordinator.get_value_from_json(
                    data,
                    self.api_endpoint,
                    self.sensor_type,
                    self.api_group,
                    self.api_tool,
                )
                return self._state
            else:
                _LOGGER.warning("Received no data from coordinator")
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Could not update sensor")
            self._available = False
        return

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    @property
    def available(self):
        return self._available
