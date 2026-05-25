"""Aqara Studio integration for Home Assistant.

This integration connects to Aqara Studio via WebSocket and exposes
Aqara devices as Home Assistant entities with real-time state sync.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_HOST, CONF_PORT, CONF_TOKEN, DEFAULT_PORT, DOMAIN, POLL_INTERVAL_FALLBACK
from .coordinator import AqaraStudioCoordinator
from .websocket_client import AqaraStudioClient, AqaraStudioWebSocketError

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.SWITCH,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.MEDIA_PLAYER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aqara Studio from a config entry."""
    host = entry.data[CONF_HOST]
    token = entry.data[CONF_TOKEN]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)

    session = async_create_clientsession(hass)
    client = AqaraStudioClient(host, token, port, session=session)

    coordinator = AqaraStudioCoordinator(hass, client)

    try:
        async with async_timeout.timeout(30):
            await client.connect()
    except (AqaraStudioWebSocketError, aiohttp.ClientError, TimeoutError) as err:
        await client.disconnect()
        raise ConfigEntryNotReady(f"Failed to connect to Aqara Studio: {err}") from err

    try:
        async with async_timeout.timeout(30):
            await coordinator.async_init()
    except (AqaraStudioWebSocketError, TimeoutError) as err:
        await client.disconnect()
        raise ConfigEntryNotReady(f"Failed to initialize Aqara Studio: {err}") from err

    # Register push event handlers
    client.set_trait_update_handler(coordinator.handle_trait_update)
    client.set_object_event_handler(coordinator.handle_object_event)

    # Store coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register stop handler
    async def _on_stop(event: Any) -> None:
        """Handle HA shutdown."""
        await client.unsubscribe_all()
        await client.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_stop)
    )

    # Start coordinator's periodic polling (fallback)
    await coordinator.async_config_entry_first_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    coordinator: AqaraStudioCoordinator | None = hass.data[DOMAIN].pop(entry.entry_id, None)
    if coordinator:
        await coordinator.client.unsubscribe_all()
        await coordinator.client.disconnect()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
