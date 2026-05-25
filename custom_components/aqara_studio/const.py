"""Constants for Aqara Studio integration."""

DOMAIN = "aqara_studio"

# --- Config Flow ---
CONF_HOST = "host"
CONF_TOKEN = "token"
CONF_PORT = "port"
DEFAULT_PORT = 80

# --- WebSocket ---
WS_SUBPROTOCOL = "aqara-studio-v1"
WS_PATH = "/open/ws"
WS_RECONNECT_INTERVAL = 10  # seconds
WS_MAX_RECONNECT_ATTEMPTS = 0  # unlimited

# --- API message types (request) ---
REQ_GET_ALL_DEVICE_INFO = "GetAllDeviceInfoRequest"
REQ_GET_DEVICE_INFO = "GetDeviceInfoRequest"
REQ_GET_DEVICES = "GetDevicesRequest"
REQ_GET_TRAIT_VALUE = "GetTraitValueRequest"
REQ_EXECUTE_TRAIT = "ExecuteTraitRequest"
REQ_SUBSCRIBE_ALL = "SubscribeAllRequest"
REQ_UNSUBSCRIBE_ALL = "UnsubscribeAllRequest"
REQ_SUBSCRIBE_TRAIT = "SubscribeTraitValueRequest"
REQ_UNSUBSCRIBE_TRAIT = "UnsubscribeTraitValueRequest"
REQ_REFRESH_TOKEN = "auth/refresh-token"
REQ_QUERY_HISTORY = "QueryDeviceHistoryDataRequest"

# --- API message types (response) ---
RSP_GET_ALL_DEVICE_INFO = "GetAllDeviceInfoResponse"
RSP_GET_DEVICE_INFO = "GetDeviceInfoResponse"
RSP_GET_DEVICES = "GetDevicesResponse"
RSP_GET_TRAIT_VALUE = "GetTraitValueResponse"
RSP_EXECUTE_TRAIT = "ExecuteTraitResponse"
RSP_SUBSCRIBE_ALL = "SubscribeAllResponse"
RSP_UNSUBSCRIBE_ALL = "UnsubscribeAllResponse"
RSP_SUBSCRIBE_TRAIT = "SubscribeTraitValueResponse"
RSP_UNSUBSCRIBE_TRAIT = "UnsubscribeTraitValueResponse"
RSP_QUERY_HISTORY = "QueryDeviceHistoryDataResponse"

# --- Push event types ---
PUSH_TRAIT_UPDATE = "TraitValueUpdate"
PUSH_OBJECT_EVENT = "objectEvent"

# --- Object event subtypes ---
EVENT_DEVICE_ADDED = "DEVICE_ADDED"
EVENT_DEVICE_REMOVED = "DEVICE_REMOVED"
EVENT_DEVICE_ONLINE = "DEVICE_ONLINE"
EVENT_DEVICE_OFFLINE = "DEVICE_OFFLINE"
EVENT_DEVICE_TRAIT_UPDATE = "DEVICE_TRAIT_PARAMETER_UPDATE"
EVENT_DEVICE_NAME_UPDATE = "DEVICE_NAME_UPDATE"

# --- Trait codes (commonly used) ---
TRAIT_ON_OFF = "OnOff"
TRAIT_CURRENT_LEVEL = "CurrentLevel"
TRAIT_COLOR_TEMPERATURE = "ColorTemperature"
TRAIT_HUE = "Hue"
TRAIT_SATURATION = "Saturation"
TRAIT_CURRENT_R = "CurrentR"
TRAIT_CURRENT_G = "CurrentG"
TRAIT_CURRENT_B = "CurrentB"
TRAIT_LOCK_STATE = "LockState"
TRAIT_TARGET_POSITION = "TargetPositionPercentage"
TRAIT_CURRENT_POSITION = "CurrentPositionPercentage"
TRAIT_SET_TEMPERATURE = "SetTemperature"
TRAIT_HEATER_COOLER_MODE = "HeaterCoolerMode"
TRAIT_FAN_MODE = "FanMode"
TRAIT_VOLUME = "Volume"
TRAIT_MUTE = "Mute"
TRAIT_TARGET_PLAYBACK = "TargetPlaybackState"
TRAIT_CURRENT_PLAYBACK = "CurrentPlaybackState"
TRAIT_FAN_SPEED = "FanSpeed"
TRAIT_BOOLEAN_STATE = "BooleanState"
TRAIT_MOTION_DETECTED = "MotionDetected"
TRAIT_OCCUPANCY = "Occupancy"
TRAIT_CONTACT_STATE = "ContactSensorState"
TRAIT_LEAK_STATE = "LeakState"
TRAIT_SMOKE_DETECTED = "SmokeDetected"
TRAIT_OCCUPANCY_SENSOR_TYPE = "OccupancySensorType"
TRAIT_BAT_LEVEL = "BatPercentRemaining"
TRAIT_TEMPERATURE = "CurrentXX"
TRAIT_HUMIDITY = "CurrentHumidity"
TRAIT_ILLUMINANCE = "CurrentIlluminance"
TRAIT_PRESSURE = "CurrentPressure"
TRAIT_CO2 = "CO2Density"
TRAIT_PM25 = "PM2.5Density"
TRAIT_PM10 = "PM10Density"
TRAIT_PM1 = "PM1.0Density"
TRAIT_VOC = "VOCDensity"
TRAIT_CURRENT_POWER = "CurrentPower"
TRAIT_CUMULATIVE_ENERGY = "CumulativeEnergyConsumption"
TRAIT_CURRENT_VOLTAGE = "CurrentVoltage"
TRAIT_CURRENT = "CircuitCurrent"
TRAIT_HEATING_TEMPERATURE = "HeatingTemperature"
TRAIT_COOLING_TEMPERATURE = "CoolingTemperature"

# --- Error codes ---
ERR_SUCCESS = 0

# --- Polling fallback ---
POLL_INTERVAL_FALLBACK = 30  # seconds, used if push is unreliable

# --- Config entry version ---
CONFIG_VERSION = 1
