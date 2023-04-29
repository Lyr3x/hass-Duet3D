"""Support for monitoring Duet3D sensors."""
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature

from . import DuetDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_ID = "duet3d_notification"
NOTIFICATION_TITLE = "Duet3d sensor setup error"

from homeassistant.const import (
    CONF_NAME,
)
from .const import (
    DOMAIN,
    SENSOR_TYPES,
    PRINTER_STATUS,
    ATTR_NAME,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the available Duet3D sensors."""
    ATTR_NAME = config_entry.data[CONF_NAME]
    coordinator: DuetDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]

    tools = coordinator.get_tools()
    device_id = config_entry.entry_id
    assert device_id is not None

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
    known_tools = set()

    @callback
    def async_add_tool_sensors() -> None:
        tool_types = ["current", "active", "standby"]
        bed_types = ["current", "active"]
        if not coordinator.data["status"]:
            return

        new_tools = []
        for tool in tools:
            if tool == "bed":
                assert device_id is not None
                for bed_type in bed_types:
                    if tool + "," + bed_type not in known_tools:
                        known_tools.add(tool + "," + bed_type)
                        new_tools.append(
                            DuetTemperatureSensor(
                                coordinator,
                                f"Tool {tool} {bed_type} temperature",
                                tool,
                                bed_type,
                                device_id,
                            )
                        )
            else:
                assert device_id is not None
                for tool_type in tool_types:
                    if str(tool) + "," + tool_type not in known_tools:
                        known_tools.add(str(tool) + "," + tool_type)
                        new_tools.append(
                            DuetTemperatureSensor(
                                coordinator,
                                f"Tool {tool} {tool_type} temperature",
                                tool,
                                tool_type,
                                device_id,
                            )
                        )
        async_add_entities(new_tools)

    config_entry.async_on_unload(coordinator.async_add_listener(async_add_tool_sensors))

    if coordinator.data["status"]:
        async_add_tool_sensors()

    entities: list[SensorEntity] = [
        DuetPrintJobPercentageSensor(coordinator, "Progress", device_id),
        DuetTimeRemainingSensor(coordinator, "Time Remaining", device_id),
        DuetPrintDurationSensor(coordinator, "Time Elapsed", device_id),
        DuetPrintPositionSensor(coordinator, "Position (X,Y,Z)", device_id),
        DuetCurrentStateSensor(coordinator, "Current state", device_id),
    ]
    async_add_entities(entities)


class DuetPrintSensorBase(CoordinatorEntity[DuetDataUpdateCoordinator], SensorEntity):
    """Representation of an Duet sensor."""

    def __init__(
        self,
        coordinator: DuetDataUpdateCoordinator,
        sensor_name: str,
        device_id: str,
    ) -> None:
        """Initialize a new Duet3D sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_name = f"{ATTR_NAME} {sensor_name}"
        self._attr_unique_id = device_id

    @property
    def device_info(self):
        """Device info."""
        return self.coordinator.device_info


class DuetTemperatureSensor(DuetPrintSensorBase):
    """Representation of an Duet sensor."""

    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: DuetDataUpdateCoordinator,
        sensor_name: str,
        tool: str,
        sensor_type: str,
        device_id: str,
    ) -> None:
        """Initialize a new Duet sensor."""
        super().__init__(
            coordinator,
            sensor_name,
            f"{tool}-{sensor_type}-{device_id}",
        )
        self._sensor_type = sensor_type
        self._api_tool = tool

    @property
    def native_value(self):
        """Return sensor state."""
        if self._api_tool == "bed":
            json_path = SENSOR_TYPES["Bed Temperatures"]["json_path"]
            bed_heater = self.coordinator.get_json_value_by_path(
                json_path + "." + self._sensor_type
            )
            if bed_heater is not None:
                return bed_heater
            else:
                return -1
        else:
            json_path = SENSOR_TYPES["Tool Temperatures"]["json_path"]
            tool_heater = self.coordinator.get_json_value_by_path(
                json_path + "." + self._sensor_type
            )
            if tool_heater is not None:
                return tool_heater
            else:
                return -1

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data["status"]["heat"]["heaters"]
        )


class DuetPrintJobPercentageSensor(DuetPrintSensorBase):
    """Representation of an Duet3D sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
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
    def native_value(self):
        """Return sensor state."""
        filament_info_json_path = SENSOR_TYPES["Progress"]["json_path"]
        job_printed_filament_json_path = SENSOR_TYPES["Filament Extrusion"]["json_path"]
        job_printed_filament = self.coordinator.get_json_value_by_path(
            job_printed_filament_json_path
        )
        filament_info = self.coordinator.get_json_value_by_path(filament_info_json_path)

        if filament_info:
            job_total_mm_of_filament = filament_info[0]
        else:
            return 0
        if job_printed_filament is not None and job_total_mm_of_filament is not None:
            progress_percentage = (
                job_printed_filament / job_total_mm_of_filament
            ) * 100
            return round(progress_percentage, 2)
        else:
            return 0


class DuetTimeRemainingSensor(DuetPrintSensorBase):
    """Representation of an Duet3D sensor."""

    _attr_native_unit_of_measurement = "min"
    # _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clock-end"

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
    def native_value(self):
        """Return sensor state."""
        time_remaining_json_path = SENSOR_TYPES["Time Remaining"]["json_path"]
        print_file_time_left = self.coordinator.get_json_value_by_path(
            time_remaining_json_path
        )
        if print_file_time_left is not None:
            return round(print_file_time_left / 60.0, 2)
        else:
            return 0


class DuetPrintDurationSensor(DuetPrintSensorBase):
    """Representation of an Duet3D sensor."""

    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT

    _attr_icon = "mdi:clock-start"

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
    def native_value(self):
        """Return sensor state."""
        json_dict = self.coordinator.data["status"]
        jobDuration = json_dict["job"]["duration"]
        if jobDuration is not None:
            return round(jobDuration / 60.0, 2)
        else:
            return 0


class DuetPrintPositionSensor(DuetPrintSensorBase):
    """Representation of an Duet3D sensor."""

    _attr_icon = "mdi:axis-x-arrow"

    def __init__(
        self,
        coordinator: DuetDataUpdateCoordinator,
        sensor_name: str,
        device_id: str,
    ) -> None:
        """Initialize a new Duet3D sensor."""
        super().__init__(
            coordinator,
            sensor_name,
            f"{sensor_name}-{device_id}",
        )

    @property
    def native_value(self):
        """Return sensor state."""
        json_dict = self.coordinator.data["status"]
        position_json_path = SENSOR_TYPES["Position"]["json_path"]
        axis_json = self.coordinator.get_json_value_by_path(position_json_path)
        positions = [
            axis_json[i]["machinePosition"]
            for i in range(len(axis_json))
            if axis_json[i]["letter"] in SENSOR_TYPES["Position"]["axes"]
        ]
        return str(positions)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data["status"]["move"]["axes"]
        )


class DuetCurrentStateSensor(DuetPrintSensorBase):
    """Representation of an Duet3D sensor."""

    _attr_icon = "mdi:printer-3d"

    def __init__(
        self,
        coordinator: DuetDataUpdateCoordinator,
        sensor_name: str,
        device_id: str,
    ) -> None:
        """Initialize a new Duet3D sensor."""
        super().__init__(
            coordinator,
            sensor_name,
            f"{sensor_name}-{device_id}",
        )

    @property
    def native_value(self):
        """Return sensor state."""
        current_state_json_path = SENSOR_TYPES["Current State"]["json_path"]
        current_state = self.coordinator.get_json_value_by_path(current_state_json_path)
        if current_state is not None and current_state in PRINTER_STATUS:
            return current_state

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data["status"]["state"]["status"]
        )
