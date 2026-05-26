"""Platform for Aqara Binary Sensor devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    TRAIT_BOOLEAN_STATE,
    TRAIT_CONTACT_STATE,
    TRAIT_LEAK_STATE,
    TRAIT_MOTION_DETECTED,
    TRAIT_OCCUPANCY,
    TRAIT_SMOKE_DETECTED,
)
from .coordinator import AqaraStudioCoordinator
from .entity import AqaraStudioEntity

_LOGGER = logging.getLogger(__name__)

# trait_code → BinarySensorDeviceClass
BINARY_MAP: dict[str, str] = {
    TRAIT_MOTION_DETECTED: BinarySensorDeviceClass.MOTION,
    TRAIT_OCCUPANCY: BinarySensorDeviceClass.OCCUPANCY,
    TRAIT_CONTACT_STATE: BinarySensorDeviceClass.DOOR,
    TRAIT_LEAK_STATE: BinarySensorDeviceClass.MOISTURE,
    TRAIT_SMOKE_DETECTED: BinarySensorDeviceClass.SMOKE,
    TRAIT_BOOLEAN_STATE: BinarySensorDeviceClass.SAFETY,
}

# device_class → icon mapping
DEVICE_CLASS_ICONS: dict[str, str] = {
    BinarySensorDeviceClass.MOTION: "mdi:motion-sensor",
    BinarySensorDeviceClass.OCCUPANCY: "mdi:account-multiple",
    BinarySensorDeviceClass.DOOR: "mdi:door",
    BinarySensorDeviceClass.MOISTURE: "mdi:water",
    BinarySensorDeviceClass.SMOKE: "mdi:smoke-detector",
    BinarySensorDeviceClass.SAFETY: "mdi:shield-check",
}

BINARY_ICON_ON: dict[str, str] = {
    BinarySensorDeviceClass.MOTION: "mdi:motion-sensor",
    BinarySensorDeviceClass.OCCUPANCY: "mdi:account-multiple",
    BinarySensorDeviceClass.DOOR: "mdi:door-open",
    BinarySensorDeviceClass.MOISTURE: "mdi:water-alert",
    BinarySensorDeviceClass.SMOKE: "mdi:smoke-detector-alert",
    BinarySensorDeviceClass.SAFETY: "mdi:shield-alert",
}

BINARY_ICON_OFF: dict[str, str] = {
    BinarySensorDeviceClass.MOTION: "mdi:motion-sensor-off",
    BinarySensorDeviceClass.OCCUPANCY: "mdi:account-multiple-outline",
    BinarySensorDeviceClass.DOOR: "mdi:door-closed",
    BinarySensorDeviceClass.MOISTURE: "mdi:water-check",
    BinarySensorDeviceClass.SMOKE: "mdi:smoke-detector-variant",
    BinarySensorDeviceClass.SAFETY: "mdi:shield-check",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aqara Studio binary_sensor platform."""
    coordinator: AqaraStudioCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for uid, config in coordinator.entity_configs.items():
        if config["platform"] != "binary_sensor":
            continue

        device_id = config["device_id"]
        spec = config.get("device_spec", {})

        # Scan for binary-sensor-like traits
        for ep in spec.get("endpoints", []):
            epid = ep.get("endpointId", 0)
            if epid == 0:
                continue
            for func in ep.get("functions", []):
                fc = func.get("functionCode", "")
                for tr in func.get("traits", []):
                    tc = tr.get("traitCode", "")
                    if tc in BINARY_MAP:
                        device_cls = BINARY_MAP[tc]
                        # Create a unique config per trait
                        suffix = f"_{tc}"
                        new_config = dict(config)
                        new_config["unique_id"] = config["unique_id"] + suffix
                        new_config["name"] = config["name"] + f"_{device_cls}"
                        entities.append(
                            AqaraStudioBinarySensor(
                                coordinator,
                                new_config,
                                trait_code=tc,
                                endpoint_id=epid,
                                function_code=fc,
                                device_class=device_cls,
                            )
                        )

    async_add_entities(entities)


class AqaraStudioBinarySensor(AqaraStudioEntity, BinarySensorEntity):
    """Representation of an Aqara binary sensor (motion, door, leak, etc.)."""

    def __init__(
        self,
        coordinator: AqaraStudioCoordinator,
        entity_config: dict,
        trait_code: str,
        endpoint_id: int,
        function_code: str,
        device_class: str,
    ) -> None:
        super().__init__(coordinator, entity_config)
        self._bs_trait_code = trait_code
        self._bs_endpoint_id = endpoint_id
        self._bs_function_code = function_code
        self._attr_device_class = device_class
        self._attr_icon = DEVICE_CLASS_ICONS.get(device_class, "mdi:toggle-switch-variant")

    @property
    def icon(self) -> str | None:
        """Return dynamic icon based on state."""
        if self.is_on:
            return BINARY_ICON_ON.get(self._attr_device_class, self._attr_icon)
        return BINARY_ICON_OFF.get(self._attr_device_class, self._attr_icon)

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on (triggered)."""
        val = self._get_trait(self._bs_endpoint_id, self._bs_function_code, self._bs_trait_code)
        if val is None:
            return None
        # For boolean traits, value is True/False
        if isinstance(val, bool):
            return val
        # For enum traits like MotionDetected, check if != "NotDetected"
        if isinstance(val, str):
            return val.lower() not in ("not_detected", "notdetected", "closed", "false", "off", "0")
        if isinstance(val, (int, float)):
            return val > 0
        return bool(val)
