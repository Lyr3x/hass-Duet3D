from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
import base64
from . import DuetDataUpdateCoordinator
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import logging
import io
from PIL import Image

_LOGGER = logging.getLogger(__name__)
from .const import (
    DOMAIN,
    SENSOR_TYPES,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    coordinator: DuetDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]
    device_id = config_entry.entry_id
    assert device_id is not None
    async_add_entities([DuetThumbnailCamera(coordinator, "Thumbnail", device_id)])


class DuetThumbnailCamera(CoordinatorEntity[DuetDataUpdateCoordinator], Camera):
    """A camera to show the Duet3D thumbnail image."""

    _attr_is_streaming = True
    _attr_motion_detection_enabled = False
    _attr_supported_features = CameraEntityFeature.ON_OFF

    def __init__(
        self,
        coordinator: DuetDataUpdateCoordinator,
        camera_name: str,
        device_id: str,
    ) -> None:
        """Initialize a new Duet thumbnail camera."""
        Camera.__init__(self)
        CoordinatorEntity.__init__(self, coordinator)
        self._device_id = device_id
        self._attr_name = f"{self.device_info['name']} {camera_name}"
        self._attr_unique_id = device_id
        self.camera_name = camera_name
        self.last_thumbnail_data = ""
        self.last_image: bytes

    @property
    def device_info(self):
        """Device info."""
        return self.coordinator.device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        job_thumbnail = self.coordinator.get_sensor_state(
            SENSOR_TYPES[self.camera_name]["json_path"], self.camera_name
        )
        return len(job_thumbnail) > 0

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        thumbnail_info_json_path = SENSOR_TYPES[self.camera_name]["json_path"]
        thumbnail_info = self.coordinator.get_sensor_state(
            thumbnail_info_json_path, self.camera_name
        )
        if self.available:
            thumbnail_data = base64.b64decode(thumbnail_info[0]["data"])
            if b"qoi" in thumbnail_data:
                thumbnail_data = self.convert_qoi_to_jpeg(thumbnail_data)

            if self.last_thumbnail_data == thumbnail_data:
                return self.last_image

            self.last_image = thumbnail_data
            return self.last_image

    def convert_qoi_to_jpeg(self, qoi_data):
        # Load QOI image from bytes
        qoi_image = Image.open(io.BytesIO(qoi_data)).convert("RGB")
        # Convert QOI image to JPEG format
        with io.BytesIO() as output:
            qoi_image.save(output, format="JPEG")
            return output.getvalue()
