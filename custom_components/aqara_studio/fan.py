"""Platform for Aqara Fan devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DOMAIN, TRAIT_FAN_SPEED, TRAIT_ON_OFF
from .coordinator import AqaraStudioCoordinator
from .entity import AqaraStudioEntity

_LOGGER = logging.getLogger(__name__)

SPEED_MIN = 1
SPEED_MAX = 100


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aqara Studio fan platform."""
    coordinator: AqaraStudioCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for uid, config in coordinator.entity_configs.items():
        if config["platform"] == "fan":
            entities.append(AqaraStudioFan(coordinator, config))
    async_add_entities(entities)


class AqaraStudioFan(AqaraStudioEntity, FanEntity):
    """Representation of an Aqara Fan."""

    _attr_icon = "mdi:fan"

    def __init__(self, coordinator: AqaraStudioCoordinator, entity_config: dict) -> None:
        super().__init__(coordinator, entity_config)
        self._attr_supported_features = FanEntityFeature.SET_SPEED
        self._attr_speed_count = int_states_in_range(SPEED_MIN, SPEED_MAX)

    @property
    def icon(self) -> str | None:
        """Return dynamic icon based on state."""
        if self.is_on:
            return "mdi:fan"
        return "mdi:fan-off"

    @property
    def is_on(self) -> bool | None:
        """Return true if fan is on."""
        return self._get_trait_for_ep(TRAIT_ON_OFF)

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        speed = self._get_trait_for_ep(TRAIT_FAN_SPEED)
        if speed is None:
            return None
        return ranged_value_to_percentage((SPEED_MIN, SPEED_MAX), int(speed))

    async def async_turn_on(self, speed: str | None = None, percentage: int | None = None, **kwargs: Any) -> None:
        """Turn the fan on."""
        commands = []
        spec = self._device_spec
        for ep in spec.get("endpoints", []):
            epid = ep.get("endpointId", 0)
            if epid == 0:
                continue
            for func in ep.get("functions", []):
                fc = func.get("functionCode", "")
                for tr in func.get("traits", []):
                    tc = tr.get("traitCode", "")
                    if tc == TRAIT_ON_OFF and tr.get("parameter", {}).get("writable"):
                        commands.append({"deviceId": self._device_id, "endpointId": epid, "functionCode": fc, "traitCode": TRAIT_ON_OFF, "value": True})
                    elif tc == TRAIT_FAN_SPEED and tr.get("parameter", {}).get("writable") and percentage is not None:
                        speed_val = round(percentage_to_ranged_value((SPEED_MIN, SPEED_MAX), percentage))
                        commands.append({"deviceId": self._device_id, "endpointId": epid, "functionCode": fc, "traitCode": TRAIT_FAN_SPEED, "value": speed_val})
        if commands:
            await self.coordinator.client.execute_trait(commands)
            for cmd in commands:
                self.coordinator.record_pending_state(
                    cmd["deviceId"], cmd["endpointId"],
                    cmd["functionCode"], cmd["traitCode"], cmd["value"]
                )
                self._set_trait(cmd["endpointId"], cmd["functionCode"], cmd["traitCode"], cmd["value"])
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._execute_trait(TRAIT_ON_OFF, False)
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan."""
        speed_val = round(percentage_to_ranged_value((SPEED_MIN, SPEED_MAX), percentage))
        await self._execute_trait(TRAIT_FAN_SPEED, speed_val)
        self.async_write_ha_state()
