"""Config flow for Aqara Studio integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONFIG_VERSION, DEFAULT_PORT, DOMAIN
from .websocket_client import AqaraStudioClient, AqaraStudioWebSocketError

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_TOKEN): str,
    }
)


async def _test_connection(
    hass: HomeAssistant, host: str, port: int, token: str
) -> dict[str, str]:
    """Test connection to Aqara Studio.

    Returns dict with "result": "ok" or error description.
    """
    session = async_create_clientsession(hass)
    client = AqaraStudioClient(host, token, port, session=session)
    try:
        await client.connect()
        # Try fetching device info to verify API works
        devices = await client.get_all_device_info()
        device_count = len(devices)
        await client.disconnect()
        return {"result": "ok", "device_count": str(device_count)}
    except AqaraStudioWebSocketError as err:
        return {"result": f"连接测试失败: {err}"}
    except Exception as err:
        return {"result": f"连接测试异常: {err}"}
    finally:
        await client.disconnect()


class AqaraStudioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aqara Studio."""

    VERSION = CONFIG_VERSION

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            token = user_input[CONF_TOKEN]

            # Test connection
            test_result = await _test_connection(self.hass, host, port, token)
            if test_result["result"] == "ok":
                # Create entry
                return self.async_create_entry(
                    title=f"Aqara Studio ({host})",
                    data=user_input,
                )
            errors["base"] = "cannot_connect"
            errors["detail"] = test_result["result"]

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "docs_link": "https://docs.aqara.com/zh/docs/aqara-studio/developer-guide"
            },
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml (not implemented)."""
        return await self.async_step_user(import_data)
