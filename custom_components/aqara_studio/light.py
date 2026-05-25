"""Platform for Aqara Light devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TRAIT_COLOR_TEMPERATURE, TRAIT_CURRENT_LEVEL, TRAIT_HUE, TRAIT_ON_OFF, TRAIT_SATURATION
from .coordinator import AqaraStudioCoordinator
from .entity import AqaraStudioEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aqara Studio light platform."""
    coordinator: AqaraStudioCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for uid, config in coordinator.entity_configs.items():
        if config["platform"] == "light":
            entities.append(AqaraStudioLight(coordinator, config))
    async_add_entities(entities)


class AqaraStudioLight(AqaraStudioEntity, LightEntity):
    """Representation of an Aqara Light."""

    def __init__(self, coordinator: AqaraStudioCoordinator, entity_config: dict) -> None:
        """Initialize light."""
        super().__init__(coordinator, entity_config)

        # Detect color modes from spec
        self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes: set[ColorMode] = set()
        spec = self._device_spec

        has_brightness = False
        has_color_temp = False
        has_hs = False

        for ep in spec.get("endpoints", []):
            for func in ep.get("functions", []):
                for tr in func.get("traits", []):
                    tc = tr.get("traitCode")
                    if tc == TRAIT_CURRENT_LEVEL:
                        has_brightness = True
                    elif tc == TRAIT_COLOR_TEMPERATURE:
                        has_color_temp = True
                    elif tc in (TRAIT_HUE, TRAIT_SATURATION):
                        has_hs = True

        if has_hs:
            self._attr_supported_color_modes.add(ColorMode.HS)
        if has_color_temp:
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
        if has_brightness and not (has_hs or has_color_temp):
            self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
        if not self._attr_supported_color_modes:
            self._attr_supported_color_modes.add(ColorMode.ONOFF)

        # Pick the current color mode
        if has_hs:
            self._attr_color_mode = ColorMode.HS
        elif has_color_temp:
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif has_brightness:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_color_mode = ColorMode.ONOFF

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._get_trait_for_ep(TRAIT_ON_OFF)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        val = self._get_trait_for_ep(TRAIT_CURRENT_LEVEL)
        if val is None:
            return None
        # Aqara reports 0..100, HA expects 0..255
        return round(val * 255 / 100)

    @property
    def color_temp(self) -> int | None:
        """Return the CT color value in mireds."""
        val = self._get_trait_for_ep(TRAIT_COLOR_TEMPERATURE)
        if val is None:
            return None
        # Aqara reports in Kelvin, HA expects mireds
        if val > 0:
            return round(1000000 / val)
        return None

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value."""
        hue = self._get_trait_for_ep(TRAIT_HUE)
        sat = self._get_trait_for_ep(TRAIT_SATURATION)
        if hue is not None and sat is not None:
            return (float(hue), float(sat))
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on.

        May include brightness, color_temp, or hs_color.
        """
        commands = []
        spec = self._device_spec

        # If currently off, send OnOff = true first
        if not self.is_on:
            for ep in spec.get("endpoints", []):
                epid = ep.get("endpointId", 0)
                if epid == 0:
                    continue
                for func in ep.get("functions", []):
                    fc = func.get("functionCode", "")
                    for tr in func.get("traits", []):
                        if tr.get("traitCode") == TRAIT_ON_OFF and tr.get("parameter", {}).get("writable"):
                            commands.append({
                                "deviceId": self._device_id,
                                "endpointId": epid,
                                "functionCode": fc,
                                "traitCode": TRAIT_ON_OFF,
                                "value": True,
                            })

        if ATTR_BRIGHTNESS in kwargs:
            val = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
            for ep in spec.get("endpoints", []):
                epid = ep.get("endpointId", 0)
                if epid == 0:
                    continue
                for func in ep.get("functions", []):
                    fc = func.get("functionCode", "")
                    for tr in func.get("traits", []):
                        if tr.get("traitCode") == TRAIT_CURRENT_LEVEL and tr.get("parameter", {}).get("writable"):
                            commands.append({
                                "deviceId": self._device_id,
                                "endpointId": epid,
                                "functionCode": fc,
                                "traitCode": TRAIT_CURRENT_LEVEL,
                                "value": val,
                            })

        if ATTR_COLOR_TEMP in kwargs:
            # Convert mireds to Kelvin
            kelvin = round(1000000 / kwargs[ATTR_COLOR_TEMP])
            for ep in spec.get("endpoints", []):
                epid = ep.get("endpointId", 0)
                if epid == 0:
                    continue
                for func in ep.get("functions", []):
                    fc = func.get("functionCode", "")
                    for tr in func.get("traits", []):
                        if tr.get("traitCode") == TRAIT_COLOR_TEMPERATURE and tr.get("parameter", {}).get("writable"):
                            commands.append({
                                "deviceId": self._device_id,
                                "endpointId": epid,
                                "functionCode": fc,
                                "traitCode": TRAIT_COLOR_TEMPERATURE,
                                "value": kelvin,
                            })

        if ATTR_HS_COLOR in kwargs:
            hue, sat = kwargs[ATTR_HS_COLOR]
            for ep in spec.get("endpoints", []):
                epid = ep.get("endpointId", 0)
                if epid == 0:
                    continue
                for func in ep.get("functions", []):
                    fc = func.get("functionCode", "")
                    for tr in func.get("traits", []):
                        tc = tr.get("traitCode")
                        if tc == TRAIT_HUE and tr.get("parameter", {}).get("writable"):
                            commands.append({
                                "deviceId": self._device_id,
                                "endpointId": epid,
                                "functionCode": fc,
                                "traitCode": TRAIT_HUE,
                                "value": float(hue),
                            })
                        elif tc == TRAIT_SATURATION and tr.get("parameter", {}).get("writable"):
                            commands.append({
                                "deviceId": self._device_id,
                                "endpointId": epid,
                                "functionCode": fc,
                                "traitCode": TRAIT_SATURATION,
                                "value": float(sat),
                            })

        if commands:
            await self.coordinator.client.execute_trait(commands)
            # Update local cache
            for cmd in commands:
                self._set_trait(cmd["endpointId"], cmd["functionCode"], cmd["traitCode"], cmd["value"])
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        spec = self._device_spec
        for ep in spec.get("endpoints", []):
            epid = ep.get("endpointId", 0)
            if epid == 0:
                continue
            for func in ep.get("functions", []):
                fc = func.get("functionCode", "")
                for tr in func.get("traits", []):
                    if tr.get("traitCode") == TRAIT_ON_OFF and tr.get("parameter", {}).get("writable"):
                        await self._execute_trait(TRAIT_ON_OFF, False, epid, fc)
                        return
