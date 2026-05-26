"""Platform for Aqara Switch / Outlet devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TRAIT_ON_OFF
from .coordinator import AqaraStudioCoordinator
from .entity import AqaraStudioEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aqara Studio switch platform."""
    coordinator: AqaraStudioCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for uid, config in coordinator.entity_configs.items():
        if config["platform"] == "switch":
            entities.append(AqaraStudioSwitch(coordinator, config))
    async_add_entities(entities)


class AqaraStudioSwitch(AqaraStudioEntity, SwitchEntity):
    """Representation of an Aqara Switch or Outlet."""

    _attr_icon = "mdi:power-socket"

    @property
    def icon(self) -> str | None:
        """Return dynamic icon based on state."""
        if self.is_on:
            return "mdi:power-socket-us"
        return "mdi:power-socket-off"

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self._get_trait_for_ep(TRAIT_ON_OFF)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._execute_trait(TRAIT_ON_OFF, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._execute_trait(TRAIT_ON_OFF, False)
        self.async_write_ha_state()
