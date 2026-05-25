"""Diagnostics support for Aqara Studio."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .coordinator import AqaraStudioCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: AqaraStudioCoordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "config_entry": entry.as_dict(),
        "connected": coordinator.client.connected,
        "device_count": len(coordinator.device_specs),
        "entity_count": len(coordinator.entity_configs),
        "trait_cache_size": len(coordinator.trait_cache),
        "devices": {
            did: {
                "name": spec.get("name"),
                "types": spec.get("deviceTypesList", []),
                "endpoint_count": len(spec.get("endpoints", [])),
            }
            for did, spec in coordinator.device_specs.items()
        },
        "entities": {
            uid: {
                "name": ec.get("name"),
                "platform": str(ec.get("platform")),
                "device_id": ec.get("device_id"),
            }
            for uid, ec in coordinator.entity_configs.items()
        },
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    coordinator: AqaraStudioCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_id = next(
        (did for did in device.identifiers if did[0] == DOMAIN),
        (None, None),
    )[1]

    if device_id and device_id in coordinator.device_specs:
        return {"spec": coordinator.device_specs[device_id]}
    return {"error": "device not found"}
