import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.util import slugify as util_slugify
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PATH,
    CONF_PORT,
    CONF_MONITORED_CONDITIONS,
    CONF_SENSORS,
    CONF_BINARY_SENSORS,
    CONF_SSL,
    TEMP_CELSIUS,
)
from .const import (
    DEFAULT_NAME,
    CONF_NUMBER_OF_TOOLS,
    CONF_BED,
    DOMAIN,
)


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
        "timesLeft.file",
        "file",
        "seconds",
        "mdi:clock-end",
    ],
    "Time Elapsed": [
        "job",
        "printDuration",
        "printTime",
        "seconds",
        "mdi:clock-start",
    ],
    "Progress": ["job", "duration", "file.printTime", "percentage", "mdi:clock-end"],
    "Position": [
        "move",
        "axes",
        "x,y,z",
        "mm,mm,mm",
        "mdi:axis-x-arrow,mdi:axis-y-arrow,mdi:axis-z-arrow",
    ],
}

BINARY_SENSOR_TYPES = {
    # API Endpoint, Group, Key, unit
    "Printing": ["job", "status", "printing", None],
}

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
                        vol.Optional(
                            CONF_PATH, default="/machine/status"
                        ): ensure_valid_path,
                        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                        vol.Required(CONF_NUMBER_OF_TOOLS, default=0): cv.positive_int,
                        vol.Optional(CONF_BED, default=False): cv.boolean,
                        vol.Optional(CONF_SENSORS, default={}): SENSOR_SCHEMA,
                        vol.Optional(
                            CONF_BINARY_SENSORS, default={}
                        ): BINARY_SENSOR_SCHEMA,
                    }
                )
            ],
            has_all_unique_names,
        ),
    },
    extra=vol.ALLOW_EXTRA,
)
