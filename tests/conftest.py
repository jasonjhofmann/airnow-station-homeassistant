"""Fixtures for the AirNow Station tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airnow_station.const import (
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    DOMAIN,
    SUBENTRY_TYPE_STATION,
)

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

MOUNTAINS_EDGE_SUBENTRY = ConfigSubentryData(
    data={
        CONF_STATION_CODE: "320030044",
        CONF_STATION_NAME: "Mountains Edge",
        CONF_LATITUDE: 36.0075,
        CONF_LONGITUDE: -115.263056,
    },
    subentry_type=SUBENTRY_TYPE_STATION,
    title="Mountains Edge",
    unique_id="320030044",
)

# A station for which SAMPLE_ROWS never contains rows: its coordinator
# sees an empty window (simulated data outage).
SILENT_STATION_SUBENTRY = ConfigSubentryData(
    data={
        CONF_STATION_CODE: "060371234",
        CONF_STATION_NAME: "Silent Station",
        CONF_LATITUDE: 34.05,
        CONF_LONGITUDE: -118.25,
    },
    subentry_type=SUBENTRY_TYPE_STATION,
    title="Silent Station",
    unique_id="060371234",
)


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
            "custom_components.airnow_station.AirNowDataAPI",
            return_value=api,
        ),
    ):
        yield api


def make_account_entry(
    subentries: bool = True,
    foreign_subentry: bool = False,
    extra_subentries: list[ConfigSubentryData] | None = None,
) -> MockConfigEntry:
    """Build an account MockConfigEntry, optionally with Mountains Edge."""
    subentries_data = [MOUNTAINS_EDGE_SUBENTRY] if subentries else []
    subentries_data.extend(extra_subentries or [])
    if foreign_subentry:
        subentries_data.append(
            ConfigSubentryData(
                data={},
                subentry_type="something_else",
                title="Foreign",
                unique_id="foreign-1",
            )
        )
    return MockConfigEntry(
        domain=DOMAIN,
        title="AirNow",
        data={CONF_API_KEY: "test-key"},
        subentries_data=subentries_data,
    )
