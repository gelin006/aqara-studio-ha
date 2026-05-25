"""Coordinator for Aqara Studio integration.

Manages the device registry, trait cache, and periodic polling fallback.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, POLL_INTERVAL_FALLBACK
from .device_mapper import map_device_to_entities
from .websocket_client import AqaraStudioClient, AqaraStudioWebSocketError

_LOGGER = logging.getLogger(__name__)


class AqaraStudioCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Aqara Studio data.

    Maintains:
      - device_specs: device_id → full spec (from GetDevicesResponse)
      - entity_configs: unique_id → entity config dict (from device_mapper)
      - trait_cache: (device_id, endpoint_id, function_code, trait_code) → value
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: AqaraStudioClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=POLL_INTERVAL_FALLBACK),
            always_update=False,
        )
        self.client = client
        self.device_specs: dict[str, dict] = {}
        self.entity_configs: dict[str, dict] = {}
        self.trait_cache: dict[tuple, Any] = {}
        self._update_queue: asyncio.Queue = asyncio.Queue()

        # device_id → set of (endpoint_id, function_code, trait_code)
        self.trait_index: dict[str, set[tuple]] = {}

    async def async_init(self) -> None:
        """Fetch device specs, build entity configs, and subscribe to pushes."""
        specs = await self.client.get_devices_spec()
        self.device_specs = {}
        for s in specs:
            did = s.get("deviceId", "")
            if did:
                self.device_specs[did] = s
                self._build_trait_index(did, s)

        # Generate HA entity configs via device_mapper
        self.entity_configs = {}
        for device_id, spec in self.device_specs.items():
            entities = map_device_to_entities(spec)
            for ent in entities:
                uid = ent["unique_id"]
                self.entity_configs[uid] = ent

        _LOGGER.info(
            "Loaded %d devices → %d entities",
            len(self.device_specs),
            len(self.entity_configs),
        )

        # Subscribe to push events
        await self.client.subscribe_all()

    def _build_trait_index(self, device_id: str, spec: dict) -> None:
        """Build a set of (endpoint_id, function_code, trait_code) for fast lookup."""
        idx: set[tuple] = set()
        for ep in spec.get("endpoints", []):
            epid = ep.get("endpointId")
            for func in ep.get("functions", []):
                fc = func.get("functionCode")
                for tr in func.get("traits", []):
                    idx.add((epid, fc, tr.get("traitCode")))
        self.trait_index[device_id] = idx

    # ── Trait Cache ──────────────────────────────────────────────────

    def get_trait_value(
        self, device_id: str, endpoint_id: int, function_code: str, trait_code: str
    ) -> Any:
        return self.trait_cache.get((device_id, endpoint_id, function_code, trait_code))

    def update_trait_cache(
        self, device_id: str, endpoint_id: int, function_code: str, trait_code: str, value: Any
    ) -> None:
        self.trait_cache[(device_id, endpoint_id, function_code, trait_code)] = value

    # ── Push Event Handlers ──────────────────────────────────────────

    async def handle_trait_update(self, msg: dict) -> None:
        """Handle TraitValueUpdate push."""
        data = msg.get("data", {})
        device_id = data.get("deviceId")
        endpoint_id = data.get("endpointId")
        function_code = data.get("functionCode")
        trait_code = data.get("traitCode")
        value = data.get("value")

        if not all([device_id, endpoint_id is not None, function_code, trait_code]):
            return

        self.update_trait_cache(device_id, endpoint_id, function_code, trait_code, value)

        # Notify via queue (consumed by platforms)
        await self._update_queue.put({
            "type": "trait_update",
            "device_id": device_id,
            "endpoint_id": endpoint_id,
            "function_code": function_code,
            "trait_code": trait_code,
            "value": value,
        })

    async def handle_object_event(self, msg: dict) -> None:
        """Handle objectEvent push (device add/remove/online/offline)."""
        data = msg.get("data", {})
        event_type = data.get("eventType")
        ev_data = data.get("data", {})
        _LOGGER.debug("objectEvent: %s", event_type)

        if event_type == "DEVICE_ADDED":
            device_id = ev_data.get("deviceId")
            if device_id:
                await self._refresh_device(device_id)

        elif event_type == "DEVICE_REMOVED":
            device_id = ev_data.get("objectId") or ev_data.get("deviceId")
            if device_id and device_id in self.device_specs:
                self.device_specs.pop(device_id, None)
                self.trait_index.pop(device_id, None)
                # Track entities to remove
                to_remove = [
                    uid for uid, ec in self.entity_configs.items()
                    if ec.get("device_id") == device_id
                ]
                for uid in to_remove:
                    self.entity_configs.pop(uid, None)
                await self._update_queue.put({
                    "type": "device_removed",
                    "device_id": device_id,
                })

        elif event_type in ("DEVICE_ONLINE", "DEVICE_OFFLINE"):
            device_id = ev_data.get("objectId") or ev_data.get("deviceId")
            await self._update_queue.put({
                "type": "device_online_offline",
                "device_id": device_id,
                "online": event_type == "DEVICE_ONLINE",
            })

    async def _refresh_device(self, device_id: str) -> None:
        """Re-fetch a single device spec after it was added to the system."""
        try:
            specs = await self.client.get_devices_spec([device_id])
            for s in specs:
                if s.get("deviceId") == device_id:
                    self.device_specs[device_id] = s
                    self._build_trait_index(device_id, s)
                    entities = map_device_to_entities(s)
                    new_configs = {}
                    for ent in entities:
                        self.entity_configs[ent["unique_id"]] = ent
                        new_configs[ent["unique_id"]] = ent
                    await self._update_queue.put({
                        "type": "device_added",
                        "device_id": device_id,
                        "entity_configs": new_configs,
                    })
                    return
            _LOGGER.warning("Device %s not found after refresh", device_id)
        except AqaraStudioWebSocketError as err:
            _LOGGER.warning("Failed to refresh device %s: %s", device_id, err)

    # ── Polling Fallback ─────────────────────────────────────────────

    async def _async_update_data(self) -> dict[str, Any]:
        """Periodic polling fallback if push is not reliable."""
        device_ids = list(self.device_specs.keys())
        if not device_ids:
            return {}
        try:
            # Build queries for all devices
            queries = []
            for did in device_ids:
                spec = self.device_specs.get(did)
                if not spec:
                    continue
                for ep in spec.get("endpoints", []):
                    epid = ep.get("endpointId", 0)
                    if epid == 0:
                        continue
                    for func in ep.get("functions", []):
                        fc = func.get("functionCode")
                        # Group all readable traits per (device, endpoint, function)
                        trait_codes = [
                            tr.get("traitCode") for tr in func.get("traits", [])
                            if tr.get("parameter", {}).get("readable")
                            and tr.get("traitCode")
                        ]
                        if trait_codes:
                            queries.append({
                                "deviceId": did,
                                "endpointId": epid,
                                "functionCode": fc,
                                "traitCodes": trait_codes,
                            })

            if not queries:
                return {}

            results = await self.client.get_trait_values(queries)
            for r in results:
                did = r.get("deviceId")
                epid = r.get("endpointId")
                fc = r.get("functionCode")
                tc = r.get("traitCode")
                val = r.get("value")
                if did and tc is not None:
                    self.update_trait_cache(did, epid, fc, tc, val)

            return {"poll": "ok", "results": len(results)}

        except AqaraStudioWebSocketError as err:
            raise UpdateFailed(f"Polling failed: {err}") from err
