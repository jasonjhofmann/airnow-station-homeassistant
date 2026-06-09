"""Fixtures for the AirNow Station tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Realistic /aq/data/ rows (dataType=B, verbose=1) for two stations, two
# hours, including the -999 partial-hour sentinel.
MOUNTAINS_EDGE = {
    "Latitude": 36.0075,
    "Longitude": -115.263056,
    "SiteName": "Mountains Edge",
    "AgencyName": "Clark County Department of Environment and Sustainability ",
    "FullAQSCode": "320030044",
    "IntlAQSCode": "840320030044",
}
OTHER_STATION = {
    "Latitude": 36.173415,
    "Longitude": -115.332728,
    "SiteName": "Palo Verde",
    "AgencyName": "Clark County Department of Environment and Sustainability ",
    "FullAQSCode": "320030075",
    "IntlAQSCode": "840320030075",
}

SAMPLE_ROWS = [
    {
        **MOUNTAINS_EDGE,
        "UTC": "2026-06-09T18:00",
        "Parameter": "OZONE",
        "Unit": "PPB",
        "Value": 50.0,
        "RawConcentration": 47.0,
        "AQI": 46,
        "Category": 1,
    },
    {
        **MOUNTAINS_EDGE,
        "UTC": "2026-06-09T19:00",
        "Parameter": "OZONE",
        "Unit": "PPB",
        "Value": 49.0,
        "RawConcentration": 47.0,
        "AQI": 45,
        "Category": 1,
    },
    {
        **MOUNTAINS_EDGE,
        "UTC": "2026-06-09T19:00",
        "Parameter": "PM2.5",
        "Unit": "UG/M3",
        "Value": 3.3,
        "RawConcentration": 3.2,
        "AQI": 18,
        "Category": 1,
    },
    # Partial current hour: Value sentinel must be skipped in favor of 19:00.
    {
        **MOUNTAINS_EDGE,
        "UTC": "2026-06-09T20:00",
        "Parameter": "PM2.5",
        "Unit": "UG/M3",
        "Value": -999.0,
        "RawConcentration": -999.0,
        "AQI": -999,
        "Category": -999,
    },
    {
        **MOUNTAINS_EDGE,
        "UTC": "2026-06-09T19:00",
        "Parameter": "PM10",
        "Unit": "UG/M3",
        "Value": 18.0,
        "RawConcentration": -999.0,
        "AQI": 17,
        "Category": 1,
    },
    # CO reports a valid concentration but no AQI (live-observed behavior).
    {
        **MOUNTAINS_EDGE,
        "UTC": "2026-06-09T19:00",
        "Parameter": "CO",
        "Unit": "PPM",
        "Value": 0.1,
        "RawConcentration": 0.1,
        "AQI": -999,
        "Category": -999,
    },
    # A second station that must be filtered out by the coordinator.
    {
        **OTHER_STATION,
        "UTC": "2026-06-09T19:00",
        "Parameter": "OZONE",
        "Unit": "PPB",
        "Value": 52.0,
        "RawConcentration": 50.0,
        "AQI": 48,
        "Category": 1,
    },
]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations in all tests."""
    yield


@pytest.fixture
def mock_api():
    """Mock AirNowDataAPI everywhere it is constructed."""
    api = MagicMock()
    api.data.bbox = AsyncMock(return_value=SAMPLE_ROWS)
    with (
        patch(
            "custom_components.airnow_station.config_flow.AirNowDataAPI",
            return_value=api,
        ),
        patch(
            "custom_components.airnow_station.coordinator.AirNowDataAPI",
            return_value=api,
        ),
    ):
        yield api
