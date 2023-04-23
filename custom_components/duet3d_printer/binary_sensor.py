"""Support for monitoring Duet3D binary sensors."""
import logging

import requests
import aiohttp
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from . import DuetDataUpdateCoordinator

from homeassistant.const import (
    CONF_NAME,
)

from .const import DOMAIN, BINARY_SENSOR_TYPES, SENSOR_TYPES, PRINTER_STATUS_DICT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the available Duet3D binary sensors."""
    name = config_entry.data[CONF_NAME]
    coordinator: DuetDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]
    device_id = config_entry.entry_id
    assert device_id is not None
    current_state_type = SENSOR_TYPES["Current State"]
    printing_type = BINARY_SENSOR_TYPES["Printing"]
    device = Duet3DBinarySensor(
        coordinator,
        device_id,
        current_state_type[2],  # key
        name,
        printing_type[2],  # name of the binary sensor
        name,
        printing_type[3],  # unit
        printing_type[0],  # group
        printing_type[1],  # endpoint
        "flags",
    )
    async_add_entities([device], True)


class DuetPrintSensorBase(
    CoordinatorEntity[DuetDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of an Duet3D sensor."""

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
        self._attr_unique_id = f"{sensor_name}-{sensor_type}-{device_id}"

    @property
    def device_info(self):
        """Device info."""
        return self.coordinator.device_info


class Duet3DBinarySensor(DuetPrintSensorBase):
    """Representation an Duet3D binary sensor."""

    def __init__(
        self,
        coordinator: DuetDataUpdateCoordinator,
        device_id: str,
        condition,
        name,
        sensor_type,
        sensor_name,
        unit,
        endpoint,
        group,
        tool=None,
    ):
        """Initialize a new Duet3D sensor."""
        super().__init__(coordinator, sensor_type, name, sensor_name, device_id)
        self.sensor_name = sensor_name
        if tool is None:
            self._name = "{} {}".format(sensor_name, condition)
        else:
            self._name = "{} {}".format(sensor_name, condition)
        self.sensor_type = sensor_type
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

        print_status_dict_lower = {k: v.lower() for k, v in PRINTER_STATUS_DICT.items()}
        casefolded_state = self._state.casefold().strip()
        if (
            casefolded_state in print_status_dict_lower.values()
            and casefolded_state in {"printing", "simulating"}
        ):
            return True
        else:
            return False

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return None

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
