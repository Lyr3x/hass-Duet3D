"""Constants for the Duet3D integration."""
from homeassistant.const import (
    TEMP_CELSIUS,
)

DOMAIN = "duet3d_printer"

DEFAULT_NAME = "Duet3D"
CONF_NAME = "name"
CONF_NUMBER_OF_TOOLS = "number_of_tools"
CONF_BED = "bed"
CONF_LIGHT = "light"
CONF_STANDALONE = "standalone"
ATTR_GCODE = "gcode"
CONF_SBC_API = "/machine"
CONF_SBC_STATUS_PATH = "/status"
CONF_SBC_GCODE_PATH = "/code"
CONF_STANDALONE_API = "/rr_model"
CONF_STANDALONE_GCODE_PATH = "rr_code"
CONF_BASE_URL = "base_url"
SERVICE_SEND_GCODE = "send_code"
CONF_INTERVAL = "update_interval"

SENSOR_TYPES = {
    "Bed Temperatures": {
        "json_path": "status.heat.heaters[0]",
        "unit": "TEMP_CELSIUS",
        "icon": "mdi:thermometer",
    },
    "Tool Temperatures": {
        "json_path": "status.heat.heaters",
        "unit": "TEMP_CELSIUS",
        "icon": "mdi:thermometer",
    },
    "Current State": {
        "json_path": "status.state.status",
        "unit": None,
        "icon": "mdi:printer-3d",
    },
    "Time Remaining": {
        "json_path": "status.job.timesLeft.file",
        "unit": "min",
        "icon": "mdi:clock-end",
    },
    "Time Elapsed": {
        "json_path": "status.job.duration",
        "unit": "min",
        "icon": "mdi:clock-start",
    },
    "Progress": {
        "json_path": "status.job.file.filament",
        "unit": "%",
        "icon": "mdi:clock-end",
    },
    "Filament Extrusion": {"json_path": "status.job.rawExtrusion"},
    "Position": {
        "json_path": "status.move.axes",
        "axes": ["X", "Y", "Z"],
        "unit": "mm,mm,mm",
        "icon": "mdi:axis-x-arrow",
    },
    "Thumbnail": {"json_path": "status.job.file.thumbnails", "icon": "mdi:picture"},
}

PRINTER_STATUS = {
    "starting",
    "simulating",
    "processing",
    "idle",
    "cancelling",
    "busy",
    "disconnected",
    "resuming",
    "halted",
    "changingTool",
    "off",
    "paused",
    "pausing" "updating",
}
