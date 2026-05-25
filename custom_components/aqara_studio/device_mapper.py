"""Aqara device type → HA platform mapping logic.

Parses the device spec (endpoints → functions → traits) from
GetDevicesResponse and decides which HA entities to create.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.const import Platform

from .const import (
    TRAIT_BOOLEAN_STATE,
    TRAIT_CO2,
    TRAIT_COLOR_TEMPERATURE,
    TRAIT_CONTACT_STATE,
    TRAIT_CURRENT_LEVEL,
    TRAIT_CURRENT_POSITION,
    TRAIT_CURRENT_POWER,
    TRAIT_CURRENT_VOLTAGE,
    TRAIT_FAN_MODE,
    TRAIT_FAN_SPEED,
    TRAIT_HUE,
    TRAIT_HUMIDITY,
    TRAIT_ILLUMINANCE,
    TRAIT_LEAK_STATE,
    TRAIT_LOCK_STATE,
    TRAIT_MOTION_DETECTED,
    TRAIT_MUTE,
    TRAIT_OCCUPANCY,
    TRAIT_ON_OFF,
    TRAIT_PM10,
    TRAIT_PM25,
    TRAIT_PRESSURE,
    TRAIT_SATURATION,
    TRAIT_SET_TEMPERATURE,
    TRAIT_SMOKE_DETECTED,
    TRAIT_TARGET_POSITION,
    TRAIT_TEMPERATURE,
    TRAIT_VOLUME,
    TRAIT_HEATER_COOLER_MODE,
)

# ── Device type → HA platform registry ──────────────────────────────
# Each entry: (device_type, match_fn, platform, entity_name_suffix)
# match_fn(traits_in_device) → bool

_DEVICE_MAP: list[tuple[str, Callable[[dict], bool], Platform, str]] = []


def _register(device_type: str, check: Callable[[dict], bool], platform: Platform, suffix: str = "") -> None:
    _DEVICE_MAP.append((device_type, check, platform, suffix))


def _has_trait(trait_code: str) -> Callable[[dict], bool]:
    """Factory: returns a checker that sees if the given trait_code exists."""
    def _check(spec: dict) -> bool:
        for ep in spec.get("endpoints", []):
            for func in ep.get("functions", []):
                for tr in func.get("traits", []):
                    if tr.get("traitCode") == trait_code:
                        return True
        return False
    return _check


def _has_any_trait(*trait_codes: str) -> Callable[[dict], bool]:
    """Factory: returns a checker that sees if ANY of the given trait_codes exist."""
    def _check(spec: dict) -> bool:
        for ep in spec.get("endpoints", []):
            for func in ep.get("functions", []):
                for tr in func.get("traits", []):
                    if tr.get("traitCode") in trait_codes:
                        return True
        return False
    return _check


def _has_write_trait(trait_code: str) -> Callable[[dict], bool]:
    """Factory: returns a checker that sees if the given trait exists AND is writable."""
    def _check(spec: dict) -> bool:
        for ep in spec.get("endpoints", []):
            for func in ep.get("functions", []):
                for tr in func.get("traits", []):
                    if tr.get("traitCode") == trait_code and tr.get("parameter", {}).get("writable"):
                        return True
        return False
    return _check


# ═══════════════════════════════════════════════════════════════════
# Register all known device mappings
# ═══════════════════════════════════════════════════════════════════

# ── Light ──
_register("Light", _has_write_trait(TRAIT_ON_OFF), Platform.LIGHT)

# ── Switch ──
_register("Switch", _has_write_trait(TRAIT_ON_OFF), Platform.SWITCH)
_register("Outlet", _has_write_trait(TRAIT_ON_OFF), Platform.SWITCH)

# ── Lock ──
_register("DoorLock", _has_trait(TRAIT_LOCK_STATE), Platform.LOCK)

# ── Cover (curtains / blinds) ──
_register("Pusher", _has_write_trait(TRAIT_TARGET_POSITION), Platform.COVER)
# Generic cover detection: has target position trait
_CoverTraitCheck = _has_write_trait(TRAIT_TARGET_POSITION)

# ── Climate (AC / thermostat) ──
_register("AirConditioner", _has_trait(TRAIT_SET_TEMPERATURE), Platform.CLIMATE)
_register("Thermostat", _has_trait(TRAIT_SET_TEMPERATURE), Platform.CLIMATE)
_register("AirConditionerController", _has_trait(TRAIT_SET_TEMPERATURE), Platform.CLIMATE)
_register("ThermostatController", _has_trait(TRAIT_SET_TEMPERATURE), Platform.CLIMATE)

# ── Fan ──
_register("Fan", _has_write_trait(TRAIT_ON_OFF), Platform.FAN)

# ── Media Player ──
_register("Speaker", _has_trait(TRAIT_VOLUME), Platform.MEDIA_PLAYER)

# ── Binary Sensors ──
_register("MotionSensor", _has_trait(TRAIT_MOTION_DETECTED), Platform.BINARY_SENSOR)
_register("OccupancySensor", _has_trait(TRAIT_OCCUPANCY), Platform.BINARY_SENSOR)
_register("ContactSensor", _has_trait(TRAIT_CONTACT_STATE), Platform.BINARY_SENSOR)
_register("WaterLeakSensor", _has_trait(TRAIT_LEAK_STATE), Platform.BINARY_SENSOR)
_register("SmokeAlarm", _has_trait(TRAIT_SMOKE_DETECTED), Platform.BINARY_SENSOR)
_register("Button", _has_trait(TRAIT_BOOLEAN_STATE), Platform.BINARY_SENSOR)
_register("OnOffSensor", _has_trait(TRAIT_BOOLEAN_STATE), Platform.BINARY_SENSOR)

# ── Sensors (numeric) ──
_register("TemperatureSensor", _has_trait(TRAIT_TEMPERATURE), Platform.SENSOR)
_register("HumiditySensor", _has_trait(TRAIT_HUMIDITY), Platform.SENSOR)
_register("IlluminanceSensor", _has_trait(TRAIT_ILLUMINANCE), Platform.SENSOR)
_register("PressureSensor", _has_trait(TRAIT_PRESSURE), Platform.SENSOR)
_register("CO2Sensor", _has_trait(TRAIT_CO2), Platform.SENSOR)
_register("AirQualitySensor", _has_any_trait(TRAIT_PM25, TRAIT_PM10), Platform.SENSOR)
_register("ElectricalSensor", _has_any_trait(TRAIT_CURRENT_POWER, TRAIT_CURRENT_VOLTAGE), Platform.SENSOR)
_register("AtmosphericPressureSensor", _has_trait(TRAIT_PRESSURE), Platform.SENSOR)


def _get_device_types(device_spec: dict) -> list[str]:
    """Get device type strings from spec."""
    return device_spec.get("deviceTypesList", [])


def _get_device_name(device_spec: dict) -> str:
    """Get device name from spec."""
    return device_spec.get("name", "Unknown Device")


def _get_device_id(device_spec: dict) -> str:
    """Get device ID from spec."""
    return device_spec.get("deviceId", "")


def _get_function_for_trait(device_spec: dict, endpoint_id: int, trait_code: str) -> dict | None:
    """Find the function that contains the given trait."""
    for ep in device_spec.get("endpoints", []):
        if ep.get("endpointId") != endpoint_id:
            continue
        for func in ep.get("functions", []):
            for tr in func.get("traits", []):
                if tr.get("traitCode") == trait_code:
                    return func
    return None


def find_writable_trait(device_spec: dict) -> tuple[int, str, str, dict] | None:
    """Find the first writable OnOff-like trait for control.

    Returns (endpoint_id, function_code, trait_code, trait_meta) or None.
    """
    for ep in device_spec.get("endpoints", []):
        epid = ep.get("endpointId", 0)
        if epid == 0:
            continue  # skip root endpoint
        for func in ep.get("functions", []):
            for tr in func.get("traits", []):
                if tr.get("parameter", {}).get("writable") and tr.get("traitCode") in (
                    TRAIT_ON_OFF, TRAIT_TARGET_POSITION, TRAIT_SET_TEMPERATURE,
                    TRAIT_VOLUME, TRAIT_LOCK_STATE,
                ):
                    return (epid, func.get("functionCode", ""), tr.get("traitCode", ""), tr)
    return None


def get_control_traits(device_spec: dict) -> list[tuple[int, str, str, dict]]:
    """Get all writable traits for a device.

    Returns list of (endpoint_id, function_code, trait_code, trait_meta).
    """
    results: list[tuple[int, str, str, dict]] = []
    for ep in device_spec.get("endpoints", []):
        epid = ep.get("endpointId", 0)
        if epid == 0:
            continue
        for func in ep.get("functions", []):
            for tr in func.get("traits", []):
                if tr.get("parameter", {}).get("writable"):
                    results.append((epid, func.get("functionCode", ""), tr.get("traitCode", ""), tr))
    return results


def get_readonly_traits(device_spec: dict) -> list[tuple[int, str, str, dict]]:
    """Get all readable traits for a device (sensor readings)."""
    results: list[tuple[int, str, str, dict]] = []
    for ep in device_spec.get("endpoints", []):
        epid = ep.get("endpointId", 0)
        for func in ep.get("functions", []):
            for tr in func.get("traits", []):
                if not tr.get("parameter", {}).get("writable", False) and tr.get("parameter", {}).get("readable", True):
                    results.append((epid, func.get("functionCode", ""), tr.get("traitCode", ""), tr))
    return results


def get_supported_color_modes(device_spec: dict) -> set[str]:
    """Detect supported color modes from traits."""
    modes: set[str] = set()
    trait_codes = set()
    for ep in device_spec.get("endpoints", []):
        for func in ep.get("functions", []):
            for tr in func.get("traits", []):
                trait_codes.add(tr.get("traitCode"))
    if TRAIT_HUE in trait_codes and TRAIT_SATURATION in trait_codes:
        modes.add("hs")
    if TRAIT_COLOR_TEMPERATURE in trait_codes:
        modes.add("color_temp")
    if TRAIT_CURRENT_LEVEL in trait_codes:
        modes.add("brightness")
    if not modes and TRAIT_ON_OFF in trait_codes:
        modes.add("onoff")
    return modes


def map_device_to_entities(device_spec: dict) -> list[dict]:
    """Map one Aqara device spec to one or more HA entity descriptors.

    Returns a list of:
      {
        "platform": Platform,
        "unique_id": str,
        "name": str,
        "device_id": str,
        "device_spec": dict,   # original spec for reference
        "primary_trait_code": str,
        "endpoint_id": int | None,
        "function_code": str | None,
      }
    """
    device_types = _get_device_types(device_spec)
    device_id = _get_device_id(device_spec)
    device_name = _get_device_name(device_spec)
    entities: list[dict] = []

    # Find the root endpoint (endpointId == 0)
    root_ep = None
    for ep in device_spec.get("endpoints", []):
        if ep.get("endpointId") == 0:
            root_ep = ep
            break

    if not root_ep:
        return entities

    matched = False
    for device_type in device_types:
        for dt, check, platform, suffix in _DEVICE_MAP:
            # Only match on device type string
            if device_type != dt:
                continue
            if not check(device_spec):
                continue
            entity_name = f"{device_name}{' ' + suffix if suffix else ''}"
            # Find primary writable trait for this platform
            control_traits = get_control_traits(device_spec)
            primary_trait = control_traits[0] if control_traits else ("", "", "", {})
            entities.append({
                "platform": platform,
                "unique_id": f"{device_id}_{platform}",
                "name": entity_name,
                "device_id": device_id,
                "device_spec": device_spec,
                "primary_trait_code": primary_trait[2],
                "endpoint_id": primary_trait[0] if primary_trait[0] else None,
                "function_code": primary_trait[1] if primary_trait[1] else None,
            })
            matched = True
            break  # only one match per device_type
        if matched:
            break

    return entities


def should_add_cover_from_trait(device_spec: dict) -> bool:
    """Check if a device (non-WindowCovering type) should be a cover via trait detection."""
    if any(t in _get_device_types(device_spec) for t in ("Pusher",)):
        return False  # already covered by direct match
    return _CoverTraitCheck(device_spec)
