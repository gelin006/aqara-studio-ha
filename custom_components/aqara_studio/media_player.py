"""Platform for Aqara Speaker (Media Player) devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TRAIT_MUTE, TRAIT_ON_OFF, TRAIT_TARGET_PLAYBACK, TRAIT_VOLUME
from .coordinator import AqaraStudioCoordinator
from .entity import AqaraStudioEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aqara Studio media_player platform."""
    coordinator: AqaraStudioCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for uid, config in coordinator.entity_configs.items():
        if config["platform"] == "media_player":
            entities.append(AqaraStudioMediaPlayer(coordinator, config))
    async_add_entities(entities)

PLAYBACK_STATE_MAP = {
    "Play": MediaPlayerState.PLAYING,
    "Pause": MediaPlayerState.PAUSED,
    "Stop": MediaPlayerState.IDLE,
}


class AqaraStudioMediaPlayer(AqaraStudioEntity, MediaPlayerEntity):
    """Representation of an Aqara Speaker / Media Player."""

    _attr_icon = "mdi:speaker-wireless"

    def __init__(self, coordinator: AqaraStudioCoordinator, entity_config: dict) -> None:
        super().__init__(coordinator, entity_config)
        self._attr_supported_features = (
            MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
        )

    @property
    def icon(self) -> str | None:
        """Return dynamic icon based on state."""
        state = self.state
        if state == MediaPlayerState.PLAYING:
            return "mdi:speaker-play"
        elif state == MediaPlayerState.PAUSED:
            return "mdi:speaker-pause"
        elif state == MediaPlayerState.OFF:
            return "mdi:speaker-off"
        return "mdi:speaker-wireless"

    @property
    def state(self) -> str | None:
        """Return the state of the media player."""
        onoff = self._get_trait_for_ep(TRAIT_ON_OFF)
        if onoff is False:
            return MediaPlayerState.OFF
        playback = self._get_trait_for_ep(TRAIT_TARGET_PLAYBACK)
        if playback:
            return PLAYBACK_STATE_MAP.get(playback, MediaPlayerState.ON)
        return MediaPlayerState.ON if onoff else MediaPlayerState.OFF

    @property
    def volume_level(self) -> float | None:
        """Volume level 0..1."""
        vol = self._get_trait_for_ep(TRAIT_VOLUME)
        if vol is not None:
            return float(vol) / 100.0
        return None

    @property
    def is_volume_muted(self) -> bool | None:
        """Return boolean if volume is currently muted."""
        return self._get_trait_for_ep(TRAIT_MUTE)

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._execute_trait(TRAIT_ON_OFF, True)
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self._execute_trait(TRAIT_ON_OFF, False)
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._execute_trait(TRAIT_VOLUME, round(volume * 100))
        self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute."""
        await self._execute_trait(TRAIT_MUTE, mute)
        self.async_write_ha_state()
