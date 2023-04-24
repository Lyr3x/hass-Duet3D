"""Support for monitoring Duet3D binary sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from . import DuetDataUpdateCoordinator

from homeassistant.const import (
    CONF_NAME,
)

from .const import DOMAIN, BINARY_SENSOR_TYPES, SENSOR_TYPES, PRINTER_STATUS_DICT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the available Duet3D binary sensors."""
    name = config_entry.data[CONF_NAME]
    coordinator: DuetDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]
    device_id = config_entry.entry_id
    assert device_id is not None

    entities: list[BinarySensorEntity] = [
        DuetPrintingSensor(coordinator, f"{name} Printing", device_id),
    ]
    async_add_entities(entities)


class DuetPrintSensorBase(
    CoordinatorEntity[DuetDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of an Duet3D sensor."""

    def __init__(
        self,
        coordinator: DuetDataUpdateCoordinator,
        sensor_name: str,
        device_id: str,
    ) -> None:
        """Initialize a new Duet3D sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_name = f"{sensor_name}"
        self._attr_unique_id = device_id

    @property
    def device_info(self):
        """Device info."""
        return self.coordinator.device_info


class DuetPrintingSensor(DuetPrintSensorBase):
    """Representation of an Duet3D sensor."""

    _attr_icon = "mdi:file-percent"

    def __init__(
        self, coordinator: DuetDataUpdateCoordinator, sensor_name: str, device_id: str
    ) -> None:
        """Initialize a new Duet3D sensor."""
        super().__init__(
            coordinator,
            sensor_name,
            f"{sensor_name}-{device_id}",
        )

    @property
    def is_on(self):
        """Return sensor state."""
        json_dict = self.coordinator.data["status"]
        printerStatus = json_dict["state"]["status"]
        if printerStatus is not None:
            print_status_dict_lower = {
                k: v.lower() for k, v in PRINTER_STATUS_DICT.items()
            }
            if printerStatus in print_status_dict_lower.values() and printerStatus in {
                "processing",
                "simulating",
            }:
                return True
            else:
                return False
        else:
            _LOGGER.warning("Received no data from coordinator")
