"""Platform for Aqara Climate (AC/Thermostat) devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    TRAIT_COOLING_TEMPERATURE,
    TRAIT_FAN_MODE,
    TRAIT_HEATER_COOLER_MODE,
    TRAIT_HEATING_TEMPERATURE,
    TRAIT_ON_OFF,
    TRAIT_SET_TEMPERATURE,
)
from .coordinator import AqaraStudioCoordinator
from .entity import AqaraStudioEntity

_LOGGER = logging.getLogger(__name__)

# Aqara HeaterCoolerMode → HA HVACMode mapping
HVAC_MODE_MAP: dict[str, str] = {
    "Heat": HVACMode.HEAT,
    "Cool": HVACMode.COOL,
    "Auto": HVACMode.AUTO,
    "Off": HVACMode.OFF,
    "FanOnly": HVACMode.FAN_ONLY,
    "Dry": HVACMode.DRY,
}

HA_TO_AQARA_HVAC = {v: k for k, v in HVAC_MODE_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aqara Studio climate platform."""
    coordinator: AqaraStudioCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for uid, config in coordinator.entity_configs.items():
        if config["platform"] == "climate":
            entities.append(AqaraStudioClimate(coordinator, config))
    async_add_entities(entities)


class AqaraStudioClimate(AqaraStudioEntity, ClimateEntity):
    """Representation of an Aqara Air Conditioner / Thermostat."""

    _attr_icon = "mdi:thermostat"

    def __init__(self, coordinator: AqaraStudioCoordinator, entity_config: dict) -> None:
        super().__init__(coordinator, entity_config)
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_target_temperature_step = 1.0
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        )

        # Detect HVAC modes from spec
        hvac_modes: set[str] = {HVACMode.OFF}
        for ep in self._device_spec.get("endpoints", []):
            for func in ep.get("functions", []):
                for tr in func.get("traits", []):
                    if tr.get("traitCode") == TRAIT_HEATER_COOLER_MODE:
                        supported = tr.get("parameter", {}).get("supportedValues", [])
                        for s in supported:
                            ha_mode = HVAC_MODE_MAP.get(s.get("key", ""), "")
                            if ha_mode:
                                hvac_modes.add(ha_mode)
        if not hvac_modes - {HVACMode.OFF}:
            hvac_modes.add(HVACMode.HEAT_COOL)
        self._attr_hvac_modes = list(hvac_modes)

        # Detect fan modes
        fan_modes: list[str] = []
        for ep in self._device_spec.get("endpoints", []):
            for func in ep.get("functions", []):
                for tr in func.get("traits", []):
                    if tr.get("traitCode") == TRAIT_FAN_MODE:
                        supported = tr.get("parameter", {}).get("supportedValues", [])
                        fan_modes = [s.get("key", "") for s in supported]
        self._attr_fan_modes = fan_modes or None

    @property
    def icon(self) -> str | None:
        """Return dynamic icon based on HVAC mode."""
        mode = self.hvac_mode
        if mode == HVACMode.COOL:
            return "mdi:snowflake"
        elif mode == HVACMode.HEAT:
            return "mdi:fire"
        elif mode == HVACMode.OFF:
            return "mdi:thermostat-off"
        return "mdi:hvac"

    @property
    def hvac_mode(self) -> str | None:
        """Return current HVAC mode."""
        onoff = self._get_trait_for_ep(TRAIT_ON_OFF)
        if onoff is False:
            return HVACMode.OFF
        mode = self._get_trait_for_ep(TRAIT_HEATER_COOLER_MODE)
        if mode is None:
            return HVACMode.HEAT_COOL if onoff else HVACMode.OFF
        return HVAC_MODE_MAP.get(mode, HVACMode.HEAT_COOL)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        val = self._get_trait_for_ep("CurrentXX")
        if val is not None:
            return float(val)
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        val = self._get_trait_for_ep(TRAIT_SET_TEMPERATURE)
        if val is not None:
            return float(val)
        # Fallback to heating/cooling temperature
        val = self._get_trait_for_ep(TRAIT_HEATING_TEMPERATURE)
        if val is not None:
            return float(val)
        val = self._get_trait_for_ep(TRAIT_COOLING_TEMPERATURE)
        if val is not None:
            return float(val)
        return None

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return self._get_trait_for_ep(TRAIT_FAN_MODE)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            # Turn off
            for ep in self._device_spec.get("endpoints", []):
                epid = ep.get("endpointId", 0)
                if epid == 0:
                    continue
                for func in ep.get("functions", []):
                    fc = func.get("functionCode", "")
                    for tr in func.get("traits", []):
                        if tr.get("traitCode") == TRAIT_ON_OFF and tr.get("parameter", {}).get("writable"):
                            await self._execute_trait(TRAIT_ON_OFF, False, epid, fc)
                            self.async_write_ha_state()
                            return
        else:
            # Turn on + set mode
            aq_mode = HA_TO_AQARA_HVAC.get(hvac_mode, "")
            commands = []
            spec = self._device_spec
            for ep in spec.get("endpoints", []):
                epid = ep.get("endpointId", 0)
                if epid == 0:
                    continue
                for func in ep.get("functions", []):
                    fc = func.get("functionCode", "")
                    for tr in func.get("traits", []):
                        tc = tr.get("traitCode", "")
                        if tc == TRAIT_ON_OFF and tr.get("parameter", {}).get("writable"):
                            commands.append({"deviceId": self._device_id, "endpointId": epid, "functionCode": fc, "traitCode": TRAIT_ON_OFF, "value": True})
                        elif tc == TRAIT_HEATER_COOLER_MODE and tr.get("parameter", {}).get("writable") and aq_mode:
                            commands.append({"deviceId": self._device_id, "endpointId": epid, "functionCode": fc, "traitCode": TRAIT_HEATER_COOLER_MODE, "value": aq_mode})
            if commands:
                await self.coordinator.client.execute_trait(commands)
                for cmd in commands:
                    self.coordinator.record_pending_state(
                        cmd["deviceId"], cmd["endpointId"],
                        cmd["functionCode"], cmd["traitCode"], cmd["value"]
                    )
                    self._set_trait(cmd["endpointId"], cmd["functionCode"], cmd["traitCode"], cmd["value"])
                self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self._execute_trait(TRAIT_SET_TEMPERATURE, float(temp))
            self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        await self._execute_trait(TRAIT_FAN_MODE, fan_mode)
        self.async_write_ha_state()
