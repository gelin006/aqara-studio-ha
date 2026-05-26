"""Platform for Aqara Cover (curtain/blind) devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TRAIT_CURRENT_POSITION, TRAIT_ON_OFF, TRAIT_TARGET_POSITION
from .coordinator import AqaraStudioCoordinator
from .entity import AqaraStudioEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aqara Studio cover platform."""
    coordinator: AqaraStudioCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for uid, config in coordinator.entity_configs.items():
        if config["platform"] == "cover":
            entities.append(AqaraStudioCover(coordinator, config))
    async_add_entities(entities)


class AqaraStudioCover(AqaraStudioEntity, CoverEntity):
    """Representation of an Aqara curtain / blind."""

    _attr_icon = "mdi:curtains"

    def __init__(self, coordinator: AqaraStudioCoordinator, entity_config: dict) -> None:
        super().__init__(coordinator, entity_config)
        self._attr_device_class = CoverDeviceClass.CURTAIN
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    @property
    def icon(self) -> str | None:
        """Return dynamic icon based on state."""
        if self.is_closed:
            return "mdi:curtains-closed"
        return "mdi:curtains"

    @property
    def is_closed(self) -> bool | None:
        """Return true if cover is fully closed (position 0)."""
        pos = self.current_cover_position
        if pos is None:
            return None
        return pos <= 0

    @property
    def current_cover_position(self) -> int | None:
        """Return current position 0 (closed) to 100 (open)."""
        val = self._get_trait_for_ep(TRAIT_CURRENT_POSITION)
        if val is None:
            # Fallback: try to derive from OnOff
            onoff = self._get_trait_for_ep(TRAIT_ON_OFF)
            if onoff is not None:
                return 100 if onoff else 0
            return None
        return int(val)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._execute_trait(TRAIT_TARGET_POSITION, 100)
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._execute_trait(TRAIT_TARGET_POSITION, 0)
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs.get("position", 50)
        await self._execute_trait(TRAIT_TARGET_POSITION, position)
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        # Some Aqara covers support a stop action via OnOff toggle or specific stop trait
        # If no stop trait exists, we just set the current position as target to halt
        await self._execute_trait(TRAIT_TARGET_POSITION, self.current_cover_position or 50)
        self.async_write_ha_state()
