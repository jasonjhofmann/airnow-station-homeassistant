"""Constants for the AirNow Station integration."""

from datetime import timedelta

DOMAIN = "airnow_station"

CONF_STATION_CODE = "station_code"
CONF_STATION_NAME = "station_name"

SUBENTRY_TYPE_STATION = "station"

# AirNow publishes hourly with some lag; poll a few times per hour.
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=15)

# How far back to query so we always span the latest published hour.
LOOKBACK_HOURS = 3

# Half-width (degrees) of the discovery box around the user's coordinates.
DISCOVERY_BBOX_DEG = 0.25

# Half-width (degrees) of the polling box around the station itself.
# ~220 m of latitude: tight enough to exclude any neighboring monitor.
STATION_BBOX_DEG = 0.002

ATTRIBUTION = "Data provided by AirNow (airnow.gov)"

AQI_CATEGORIES = {
    1: "Good",
    2: "Moderate",
    3: "Unhealthy for Sensitive Groups",
    4: "Unhealthy",
    5: "Very Unhealthy",
    6: "Hazardous",
}
