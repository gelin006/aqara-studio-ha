"""WebSocket client for Aqara Studio data export API v1."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine

import aiohttp

from .const import (
    ERR_SUCCESS,
    PUSH_OBJECT_EVENT,
    PUSH_TRAIT_UPDATE,
    REQ_EXECUTE_TRAIT,
    REQ_GET_ALL_DEVICE_INFO,
    REQ_GET_DEVICES,
    REQ_GET_TRAIT_VALUE,
    REQ_SUBSCRIBE_ALL,
    REQ_UNSUBSCRIBE_ALL,
    WS_PATH,
    WS_RECONNECT_INTERVAL,
    WS_SUBPROTOCOL,
)

_LOGGER = logging.getLogger(__name__)

MessageHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class AqaraStudioWebSocketError(Exception):
    """Generic WebSocket error."""


class AqaraStudioConnectionClosed(AqaraStudioWebSocketError):
    """Connection closed unexpectedly."""


class AqaraStudioClient:
    """WebSocket client for Aqara Studio data export API v1.

    Communicates via JSON-RPC-like messages over WebSocket.
    All requests/response are paired via msgId.
    Push events (TraitValueUpdate, objectEvent) arrive asynchronously.
    """

    def __init__(
        self,
        host: str,
        token: str,
        port: int = 443,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._host = host
        self._token = token
        self._port = port
        self._session = session

        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._connected = False
        self._closing = False
        self._recv_task: asyncio.Task | None = None

        # Pending request callbacks: msgId -> asyncio.Future
        self._pending: dict[str, asyncio.Future] = {}
        self._msg_counter = 0

        # Push event handlers
        self._trait_update_handler: MessageHandler | None = None
        self._object_event_handler: MessageHandler | None = None

        # Connection lifecycle callbacks
        self._on_connected: Callable[[], Coroutine[Any, Any, None]] | None = None
        self._on_disconnected: Callable[[], Coroutine[Any, Any, None]] | None = None

    # ── Configuration ────────────────────────────────────────────────

    def set_trait_update_handler(self, handler: MessageHandler) -> None:
        self._trait_update_handler = handler

    def set_object_event_handler(self, handler: MessageHandler) -> None:
        self._object_event_handler = handler

    def set_connection_handlers(
        self,
        on_connected: Callable[[], Coroutine[Any, Any, None]] | None = None,
        on_disconnected: Callable[[], Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected

    # ── Properties ──

    @property
    def connected(self) -> bool:
        return self._connected

    # ── Connection Management ────────────────────────────────────────

    def _ws_url(self) -> str:
        scheme = "wss" if self._port == 443 else "ws"
        return f"{scheme}://{self._host}:{self._port}{WS_PATH}"

    async def connect(self) -> None:
        """Establish WebSocket connection with Bearer auth."""
        url = self._ws_url()
        _LOGGER.debug("Connecting: %s", url)

        # NOTE: The token from Aqara Studio may already include a "Bearer " prefix.
        # If it does, use it as-is per the documentation.
        auth_header = (
            self._token
            if self._token.startswith("Bearer ")
            else f"Bearer {self._token}"
        )

        ws_session = self._session or aiohttp.ClientSession()
        self._ws = await ws_session.ws_connect(
            url,
            headers={"Authorization": auth_header},
            heartbeat=30.0,
        )

        # Aqara Studio authenticates via Bearer token in HTTP headers during the WebSocket upgrade.
        # No separate auth confirmation message is sent; the connection is ready once established.
        _LOGGER.debug("WebSocket upgrade complete: %s:%s", self._host, self._port)

        self._connected = True
        _LOGGER.info("Connected to Aqara Studio at %s:%s", self._host, self._port)

        if self._on_connected:
            asyncio.create_task(self._on_connected())

        self._recv_task = asyncio.create_task(self._recv_loop())

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        self._closing = True
        if self._recv_task and not self._recv_task.done():
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._connected = False

    async def reconnect(self) -> None:
        """Keep trying to reconnect until closing."""
        while not self._closing:
            try:
                await self.connect()
                return
            except Exception as err:
                _LOGGER.warning("Reconnect failed, retry in %ss: %s", WS_RECONNECT_INTERVAL, err)
                await asyncio.sleep(WS_RECONNECT_INTERVAL)

    # ── Request/Response ─────────────────────────────────────────────

    async def _next_msg_id(self) -> str:
        self._msg_counter += 1
        return f"ha_{self._msg_counter}"

    async def send_request(self, msg_type: str, data: Any = None) -> dict:
        """Send a request and wait for the paired response.

        Args:
            msg_type: The 'type' field value (e.g. 'GetAllDeviceInfoRequest')
            data: The 'data' field value. Can be a dict, list, or None.

        Returns:
            The full response dict (including type, code, msgId, data).
        """
        if not self._ws or self._ws.closed:
            raise AqaraStudioConnectionClosed("WebSocket not connected")

        msg_id = await self._next_msg_id()
        msg: dict = {"type": msg_type, "version": "v1", "msgId": msg_id}
        if data is not None:
            msg["data"] = data

        future: asyncio.Future = asyncio.Future()
        self._pending[msg_id] = future

        _LOGGER.debug(">> %s (%s)", msg_type, msg_id)
        try:
            await self._ws.send_json(msg)
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            raise AqaraStudioWebSocketError(f"Request {msg_type} timed out") from None
        finally:
            self._pending.pop(msg_id, None)

    # ── Receive Loop ─────────────────────────────────────────────────

    async def _recv_loop(self) -> None:
        """Continuously receive and dispatch messages."""
        try:
            async for raw in self._ws:
                if self._closing:
                    break
                try:
                    msg = raw.json() if isinstance(raw.data, (str, bytes)) else raw.data
                except (json.JSONDecodeError, TypeError) as err:
                    _LOGGER.warning("Invalid JSON: %s", err)
                    continue
                await self._dispatch(msg)
        except asyncio.CancelledError:
            pass
        except Exception as err:
            _LOGGER.error("Recv error: %s", err)
        finally:
            was = self._connected
            self._connected = False
            if was and not self._closing:
                _LOGGER.info("Disconnected, reconnecting...")
                if self._on_disconnected:
                    asyncio.create_task(self._on_disconnected())
                asyncio.create_task(self.reconnect())

    async def _dispatch(self, msg: dict) -> None:
        """Route incoming message to pending future or push handler."""
        msg_type = msg.get("type", "")
        msg_id = msg.get("msgId", "")

        # 1) Response to a pending request
        if msg_id in self._pending:
            fut = self._pending[msg_id]
            if not fut.done():
                fut.set_result(msg)
            return

        # 2) Push events
        if msg_type == PUSH_TRAIT_UPDATE and self._trait_update_handler:
            asyncio.create_task(self._trait_update_handler(msg))
        elif msg_type == PUSH_OBJECT_EVENT and self._object_event_handler:
            asyncio.create_task(self._object_event_handler(msg))
        else:
            _LOGGER.debug("Unhandled: type=%s id=%s", msg_type, msg_id)

    # ── High-Level API Methods ───────────────────────────────────────

    async def get_all_device_info(self) -> list[dict]:
        """Get basic info for all devices.

        Response data is a list: [{deviceId, deviceName, deviceTypesList, createTime, state}, ...]
        """
        resp = await self.send_request(REQ_GET_ALL_DEVICE_INFO)
        if resp.get("code") != ERR_SUCCESS:
            raise AqaraStudioWebSocketError(f"GetAllDeviceInfo failed: {resp.get('message')}")
        return resp.get("data", [])

    async def get_devices_spec(self, device_ids: list[str] | None = None) -> list[dict]:
        """Get full spec (endpoints → functions → traits) for devices.

        Response data is a list: [{deviceId, name, deviceTypesList, endpoints: [...]}, ...]

        Args:
            device_ids: List of device IDs to query. None = all devices.
        """
        data = {"deviceIds": device_ids} if device_ids else {}
        resp = await self.send_request(REQ_GET_DEVICES, data)
        if resp.get("code") != ERR_SUCCESS:
            raise AqaraStudioWebSocketError(f"GetDevices failed: {resp.get('message')}")
        return resp.get("data", [])

    async def get_trait_values(
        self, queries: list[dict]
    ) -> list[dict]:
        """Get current trait values.

        Args:
            queries: [{deviceId, endpointId, functionCode, traitCodes: [...]}, ...]

        Returns list of: [{deviceId, endpointId, functionCode, traitCode, value, time}, ...]
        """
        resp = await self.send_request(REQ_GET_TRAIT_VALUE, queries)
        if resp.get("code") != ERR_SUCCESS:
            raise AqaraStudioWebSocketError(f"GetTraitValue failed: {resp.get('message')}")
        return resp.get("data", [])

    async def execute_trait(
        self, commands: list[dict]
    ) -> dict:
        """Control devices by writing trait values.

        Args:
            commands: [{deviceId, endpointId, functionCode, traitCode, value}, ...]

        Returns the response data (failed commands list).
        """
        resp = await self.send_request(REQ_EXECUTE_TRAIT, commands)
        if resp.get("code") != ERR_SUCCESS:
            raise AqaraStudioWebSocketError(f"ExecuteTrait failed: {resp.get('message')}")
        return resp.get("data", [])

    async def subscribe_all(self) -> None:
        """Subscribe to all trait value changes across all devices."""
        resp = await self.send_request(REQ_SUBSCRIBE_ALL)
        if resp.get("code") != ERR_SUCCESS:
            raise AqaraStudioWebSocketError(f"SubscribeAll failed: {resp.get('message')}")
        _LOGGER.info("Subscribed to all trait updates")

    async def unsubscribe_all(self) -> None:
        """Unsubscribe from all trait value changes."""
        try:
            await self.send_request(REQ_UNSUBSCRIBE_ALL)
        except AqaraStudioConnectionClosed:
            pass
        _LOGGER.info("Unsubscribed")
