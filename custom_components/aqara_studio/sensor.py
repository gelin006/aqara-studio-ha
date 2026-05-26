"""Platform for Aqara Sensor devices (numeric sensors)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfElectricPotential,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    TRAIT_BAT_LEVEL,
    TRAIT_CO2,
    TRAIT_CUMULATIVE_ENERGY,
    TRAIT_CURRENT,
    TRAIT_CURRENT_POWER,
    TRAIT_CURRENT_VOLTAGE,
    TRAIT_HUMIDITY,
    TRAIT_ILLUMINANCE,
    TRAIT_PM10,
    TRAIT_PM25,
    TRAIT_PRESSURE,
    TRAIT_TEMPERATURE,
)
from .coordinator import AqaraStudioCoordinator
from .entity import AqaraStudioEntity

_LOGGER = logging.getLogger(__name__)

# Trait code → sensor descriptor mapping
# Each entry: (trait_code, device_class, state_class, unit_of_measurement, friendly_name_prefix, icon)
SENSOR_MAP: dict[str, tuple[str, str, str, str, str]] = {
    TRAIT_TEMPERATURE: (
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
        UnitOfTemperature.CELSIUS,
        "温度",
        "mdi:thermometer",
    ),
    TRAIT_HUMIDITY: (
        SensorDeviceClass.HUMIDITY,
        SensorStateClass.MEASUREMENT,
        PERCENTAGE,
        "湿度",
        "mdi:water-percent",
    ),
    TRAIT_ILLUMINANCE: (
        SensorDeviceClass.ILLUMINANCE,
        SensorStateClass.MEASUREMENT,
        LIGHT_LUX,
        "光照度",
        "mdi:brightness-5",
    ),
    TRAIT_PRESSURE: (
        SensorDeviceClass.PRESSURE,
        SensorStateClass.MEASUREMENT,
        UnitOfPressure.KPA,
        "气压",
        "mdi:gauge",
    ),
    TRAIT_CO2: (
        SensorDeviceClass.CO2,
        SensorStateClass.MEASUREMENT,
        CONCENTRATION_PARTS_PER_MILLION,
        "CO₂",
        "mdi:molecule-co2",
    ),
    TRAIT_PM25: (
        SensorDeviceClass.PM25,
        SensorStateClass.MEASUREMENT,
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "PM2.5",
        "mdi:air-filter",
    ),
    TRAIT_PM10: (
        SensorDeviceClass.PM10,
        SensorStateClass.MEASUREMENT,
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "PM10",
        "mdi:air-purifier",
    ),
    TRAIT_CURRENT_POWER: (
        SensorDeviceClass.POWER,
        SensorStateClass.MEASUREMENT,
        UnitOfPower.WATT,
        "功率",
        "mdi:flash-outline",
    ),
    TRAIT_CURRENT_VOLTAGE: (
        SensorDeviceClass.VOLTAGE,
        SensorStateClass.MEASUREMENT,
        UnitOfElectricPotential.VOLT,
        "电压",
        "mdi:sine-wave",
    ),
    TRAIT_CURRENT: (
        SensorDeviceClass.CURRENT,
        SensorStateClass.MEASUREMENT,
        "A",
        "电流",
        "mdi:current-ac",
    ),
    TRAIT_CUMULATIVE_ENERGY: (
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL_INCREASING,
        UnitOfEnergy.WATT_HOUR,
        "累计耗电",
        "mdi:lightning-bolt",
    ),
    TRAIT_BAT_LEVEL: (
        SensorDeviceClass.BATTERY,
        SensorStateClass.MEASUREMENT,
        PERCENTAGE,
        "电量",
        "mdi:battery",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aqara Studio sensor platform."""
    coordinator: AqaraStudioCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for uid, config in coordinator.entity_configs.items():
        if config["platform"] != "sensor":
            continue

        # For sensor-type devices, we may need to create multiple HA sensors
        # (e.g., a TemperatureSensor device has temperature + possibly humidity)
        device_id = config["device_id"]
        spec = config.get("device_spec", {})

        # Scan all endpoints for readable numeric traits that are sensor-like
        for ep in spec.get("endpoints", []):
            epid = ep.get("endpointId", 0)
            for func in ep.get("functions", []):
                fc = func.get("functionCode", "")
                for tr in func.get("traits", []):
                    tc = tr.get("traitCode", "")
                    if tc in SENSOR_MAP:
                        device_cls, state_cls, unit, prefix, icon = SENSOR_MAP[tc]
                        unique_suffix = f"{epid}_{fc}_{tc}"
                        entities.append(
                            AqaraStudioSensor(
                                coordinator,
                                config,
                                trait_code=tc,
                                endpoint_id=epid,
                                function_code=fc,
                                device_class=device_cls,
                                state_class=state_cls,
                                unit=unit,
                                icon=icon,
                                suffix=f"_{prefix}",
                            )
                        )

    async_add_entities(entities)


class AqaraStudioSensor(AqaraStudioEntity, SensorEntity):
    """Representation of an Aqara numeric sensor (temperature, humidity, etc.)."""

    def __init__(
        self,
        coordinator: AqaraStudioCoordinator,
        entity_config: dict,
        trait_code: str,
        endpoint_id: int | None,
        function_code: str | None,
        device_class: str,
        state_class: str,
        unit: str,
        icon: str,
        suffix: str = "",
    ) -> None:
        """Initialize sensor."""
        # Override unique_id and name for the specific trait
        self._trait_code = trait_code
        self._sensor_endpoint_id = endpoint_id
        self._sensor_function_code = function_code

        new_config = dict(entity_config)
        new_config["unique_id"] = entity_config["unique_id"] + suffix
        new_config["name"] = entity_config["name"] + suffix
        super().__init__(coordinator, new_config)

        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon

    @property
    def native_value(self):
        """Return the sensor value."""
        return self._get_trait(
            self._sensor_endpoint_id,
            self._sensor_function_code,
            self._trait_code,
        )
