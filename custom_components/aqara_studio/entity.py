"""Base entity for Aqara Studio integration."""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AqaraStudioCoordinator

_LOGGER = logging.getLogger(__name__)


class AqaraStudioEntity(CoordinatorEntity[AqaraStudioCoordinator]):
    """Base entity for all Aqara Studio platforms.

    Provides:
    - Coordinator access
    - Device info (via device_spec)
    - Trait cache read/write helpers
    - Push event processing with stale-state debounce
    """

    def __init__(
        self,
        coordinator: AqaraStudioCoordinator,
        entity_config: dict,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self._entity_config = entity_config
        self._device_id: str = entity_config["device_id"]
        self._device_spec: dict = entity_config.get("device_spec", {})
        self._attr_unique_id = entity_config["unique_id"]
        self._attr_name = entity_config["name"]

        # Device info for HA device registry
        device_name = self._device_spec.get("name", "Unknown Aqara Device")
        device_types = self._device_spec.get("deviceTypesList", [])
        model = device_types[0] if device_types else "Unknown"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=device_name,
            manufacturer="Aqara",
            model=model,
            via_device=(DOMAIN, "aqara_studio_hub"),
        )

        # Primary control trait info
        self._primary_trait_code = entity_config.get("primary_trait_code", "")
        self._endpoint_id = entity_config.get("endpoint_id")
        self._function_code = entity_config.get("function_code")

    # ── Trait Cache Helpers ──────────────────────────────────────────

    def _get_trait(self, ep_id: int | None, func_code: str | None, trait_code: str) -> Any | None:
        """Get cached trait value."""
        if ep_id is None:
            ep_id = 0
        if func_code is None:
            func_code = ""
        return self.coordinator.get_trait_value(self._device_id, ep_id, func_code, trait_code)

    def _set_trait(self, ep_id: int | None, func_code: str | None, trait_code: str, value: Any) -> None:
        """Update cached trait value."""
        if ep_id is None:
            ep_id = 0
        if func_code is None:
            func_code = ""
        self.coordinator.update_trait_cache(self._device_id, ep_id, func_code, trait_code, value)

    def _get_trait_for_ep(self, trait_code: str) -> Any | None:
        """Get trait value from the first endpoint that has it (auto-detect endpoint)."""
        for ep in self._device_spec.get("endpoints", []):
            epid = ep.get("endpointId", 0)
            if epid == 0:
                continue
            for func in ep.get("functions", []):
                fc = func.get("functionCode", "")
                for tr in func.get("traits", []):
                    if tr.get("traitCode") == trait_code:
                        return self._get_trait(epid, fc, trait_code)
        return None

    # ── Control Helper (with stale-state debounce) ───────────────────

    async def _execute_trait(self, trait_code: str, value: Any,
                             ep_id: int | None = None, func_code: str | None = None) -> None:
        """Send a control command to Aqara Studio.

        Immediately updates local cache and records the pending command
        so stale push events (pre-command state) are ignored.
        """
        epid = ep_id if ep_id is not None else self._endpoint_id
        fcode = func_code if func_code is not None else self._function_code
        if epid is None or not fcode:
            _LOGGER.error("Missing endpoint/function for execute_trait on %s", self.entity_id)
            return

        # Send command to device
        await self.coordinator.client.execute_trait([{
            "deviceId": self._device_id,
            "endpointId": epid,
            "functionCode": fcode,
            "traitCode": trait_code,
            "value": value,
        }])

        # Record the pending state so stale-old-state pushes get ignored
        self.coordinator.record_pending_state(
            self._device_id, epid, fcode, trait_code, value
        )

        # Optimistic local update
        self._set_trait(epid, fcode, trait_code, value)

    # ── Availability from device online/offline ────────────────────────

    @property
    def available(self) -> bool:
        """Return True if the device is online."""
        online_trait = self._get_trait(0, "", "OnlineState")
        if online_trait is not None:
            return bool(online_trait)
        return True  # default to available if unknown

    # ── State update from push events ────────────────────────────────

    async def async_trait_update(self, endpoint_id: int, function_code: str,
                                  trait_code: str, value: Any) -> None:
        """Called when a TraitValueUpdate arrives for this entity.

        Override in subclass to update HA state.
        """
        self._set_trait(endpoint_id, function_code, trait_code, value)
        self.async_write_ha_state()
