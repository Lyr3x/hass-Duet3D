"""Constants for the Duet3D integration."""

DOMAIN = "duet3d_printer"

DEFAULT_NAME = "Duet3D"
CONF_NAME = "name"
CONF_NUMBER_OF_TOOLS = "number_of_tools"
CONF_BED = "bed"
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

