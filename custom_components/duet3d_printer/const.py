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
ATTR_GCODE = "gcode"
CONF_API = "/machine"
CONF_STATUS_PATH = "/status"
CONF_GCODE_PATH = "/code"
CONF_BASE_URL = "base_url"
SERVICE_SEND_GCODE = "send_code"
CONF_MONITORED_CONDITIONS = "monitored_conditions"
MONITORED_CONDITIONS = [
    "Current State",
    "Temperatures",
    "Time Elapsed",
    "Time Remaining",
    "Position",
    "Progress",
]

SENSOR_TYPES = {
    # API Endpoint, Group, Key, unit, icon
    # Group, subgroup, key, unit, icon
    "Temperatures": [
        "heat",
        "heaters",
        "*",
        TEMP_CELSIUS,
        "mdi:thermometer",
    ],
    "Current State": [
        "state",
        "state.status",
        "status",
        None,
        "mdi:printer-3d",
    ],
    "Time Remaining": [
        "job",
        "timesLeft",
        "file",
        "min",
        "mdi:clock-end",
    ],
    "Time Elapsed": [
        "job",
        "duration",
        "duration",
        "min",
        "mdi:clock-start",
    ],
    "Progress": ["job", "progress", "file.printTime", "%", "mdi:clock-end"],
    "Position": [
        "move",
        "axes",
        "x,y,z",
        "mm,mm,mm",
        "mdi:axis-x-arrow",
    ],
}

BINARY_SENSOR_TYPES = {
    # API Endpoint, Group, Key, unit
    "Printing": ["state", "state.status", "status", None, None],
}

PRINTER_STATUS_DICT = {
            "S": "Stopped",
            "M": "Simulating",
            "P": "Printing",
            "I": "Idle",
            "C": "Configuring",
            "B": "Busy",
            "D": "Decelerating",
            "R": "Resuming",
            "H": "Halted",
            "F": "Flashing Firmware",
            "T": "Changing Tool",
        }
