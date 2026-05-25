"""Platform for Aqara Door Lock devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import LockEntity, LockEntityFeature, LockState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TRAIT_LOCK_STATE
from .coordinator import AqaraStudioCoordinator
from .entity import AqaraStudioEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aqara Studio lock platform."""
    coordinator: AqaraStudioCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for uid, config in coordinator.entity_configs.items():
        if config["platform"] == "lock":
            entities.append(AqaraStudioLock(coordinator, config))
    async_add_entities(entities)


LOCK_STATE_MAP = {
    "LOCKED": LockState.LOCKED,
    "UNLOCKED": LockState.UNLOCKED,
    "LOCKING": LockState.LOCKING,
    "UNLOCKING": LockState.UNLOCKING,
    "JAMMED": LockState.JAMMED,
}


class AqaraStudioLock(AqaraStudioEntity, LockEntity):
    """Representation of an Aqara Door Lock."""

    @property
    def is_locked(self) -> bool | None:
        """Return true if the lock is locked."""
        val = self._get_trait_for_ep(TRAIT_LOCK_STATE)
        if val is None:
            return None
        if isinstance(val, str):
            return val.upper() in ("LOCKED", "LOCK")
        return bool(val)

    @property
    def lock_state(self) -> LockState | None:
        """Return the lock state."""
        val = self._get_trait_for_ep(TRAIT_LOCK_STATE)
        if val is None:
            return None
        if isinstance(val, str):
            return LOCK_STATE_MAP.get(val.upper())
        return LockState.LOCKED if val else LockState.UNLOCKED

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the door."""
        await self._execute_trait(TRAIT_LOCK_STATE, "LOCKED")
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the door."""
        await self._execute_trait(TRAIT_LOCK_STATE, "UNLOCKED")
        self.async_write_ha_state()
