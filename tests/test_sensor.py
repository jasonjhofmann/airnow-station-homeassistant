"""Tests for AirNow Station sensors."""

from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.airnow_station.const import DOMAIN

from .conftest import make_account_entry


def state_by_unique_id(hass: HomeAssistant, unique_id: str):
    """Look up a sensor state via its registry unique_id."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id, f"no entity registered for {unique_id}"
    return hass.states.get(entity_id)


async def test_sensors(hass: HomeAssistant, mock_api) -> None:
    """Sensors expose the latest valid row per parameter."""
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ozone = state_by_unique_id(hass, "320030044-ozone")
    assert ozone.state == "49.0"
    assert ozone.attributes["observed_utc"] == "2026-06-09T19:00"
    assert ozone.attributes["raw_concentration"] == 47.0

    # 20:00 sentinel row skipped: PM2.5 comes from 19:00.
    pm25 = state_by_unique_id(hass, "320030044-pm25")
    assert pm25.state == "3.3"
    assert (
        pm25.attributes["unit_of_measurement"]
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    # -999 raw concentration is not exposed as an attribute.
    pm10 = state_by_unique_id(hass, "320030044-pm10")
    assert pm10.state == "18.0"
    assert "raw_concentration" not in pm10.attributes

    assert state_by_unique_id(hass, "320030044-pm25_aqi").state == "18"

    # Overall AQI = max across pollutants; the other station's higher
    # ozone row (AQI 48) must have been filtered out.
    overall = state_by_unique_id(hass, "320030044-aqi")
    assert overall.state == "45"
    assert overall.attributes["dominant_pollutant"] == "OZONE"
    assert overall.attributes["category"] == "Good"

    # CO has a concentration but its -999 AQI maps to unknown.
    assert state_by_unique_id(hass, "320030044-co").state == "0.1"
    assert state_by_unique_id(hass, "320030044-co_aqi").state == "unknown"

    # No NO2/SO2 entities for a station that doesn't report them.
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, "320030044-no2") is None


async def test_entities_bound_to_subentry(hass: HomeAssistant, mock_api) -> None:
    """Entities and device are associated with the station subentry."""
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    subentry_id = next(iter(entry.subentries))
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, "320030044-aqi")
    entity_entry = registry.async_get(entity_id)
    assert entity_entry.config_subentry_id == subentry_id


async def test_unknown_parameter_ignored(hass: HomeAssistant, mock_api) -> None:
    """A parameter with no sensor description creates no entity."""
    from .conftest import MOUNTAINS_EDGE, SAMPLE_ROWS

    mock_api.data.bbox.return_value = SAMPLE_ROWS + [
        {
            **MOUNTAINS_EDGE,
            "UTC": "2026-06-09T19:00",
            "Parameter": "NOX",
            "Unit": "PPB",
            "Value": 5.0,
            "RawConcentration": 5.0,
            "AQI": 1,
            "Category": 1,
        }
    ]
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, "320030044-nox") is None
    # Overall AQI unaffected by the low-AQI unknown parameter.
    assert state_by_unique_id(hass, "320030044-aqi").state == "45"


async def test_parameter_disappearing_marks_unavailable(
    hass: HomeAssistant, mock_api
) -> None:
    """A parameter missing from a later update goes unavailable."""
    from .conftest import SAMPLE_ROWS

    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert state_by_unique_id(hass, "320030044-ozone").state == "49.0"

    # Next poll: only PM2.5 reports.
    mock_api.data.bbox.return_value = [
        row for row in SAMPLE_ROWS if row["Parameter"] == "PM2.5"
    ]
    coordinator = next(iter(entry.runtime_data.values()))
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert state_by_unique_id(hass, "320030044-ozone").state == "unavailable"
    assert state_by_unique_id(hass, "320030044-pm25").state == "3.3"
    overall = state_by_unique_id(hass, "320030044-aqi")
    assert overall.state == "18"
    assert overall.attributes["dominant_pollutant"] == "PM2.5"


async def test_overall_aqi_unknown_when_no_valid_aqi(
    hass: HomeAssistant, mock_api
) -> None:
    """Only sentinel AQIs (e.g. CO-only station) -> overall AQI unknown."""
    from .conftest import MOUNTAINS_EDGE

    mock_api.data.bbox.return_value = [
        {
            **MOUNTAINS_EDGE,
            "UTC": "2026-06-09T19:00",
            "Parameter": "CO",
            "Unit": "PPM",
            "Value": 0.1,
            "RawConcentration": 0.1,
            "AQI": -999,
            "Category": -999,
        }
    ]
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert state_by_unique_id(hass, "320030044-co").state == "0.1"
    overall = state_by_unique_id(hass, "320030044-aqi")
    assert overall.state == "unknown"
    assert "dominant_pollutant" not in overall.attributes


async def test_null_value_row_falls_back_to_prior_hour(
    hass: HomeAssistant, mock_api
) -> None:
    """A JSON null Value is skipped like the -999 sentinel, not crashed on."""
    from .conftest import MOUNTAINS_EDGE

    mock_api.data.bbox.return_value = [
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
        {
            **MOUNTAINS_EDGE,
            "UTC": "2026-06-09T20:00",
            "Parameter": "PM2.5",
            "Unit": "UG/M3",
            "Value": None,
            "RawConcentration": None,
            "AQI": None,
            "Category": None,
        },
    ]
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    pm25 = state_by_unique_id(hass, "320030044-pm25")
    assert pm25.state == "3.3"
    assert pm25.attributes["observed_utc"] == "2026-06-09T19:00"


async def test_missing_aqi_key_reports_concentration_only(
    hass: HomeAssistant, mock_api
) -> None:
    """A row without an AQI key still reports its concentration."""
    from .conftest import MOUNTAINS_EDGE

    mock_api.data.bbox.return_value = [
        {
            **MOUNTAINS_EDGE,
            "UTC": "2026-06-09T19:00",
            "Parameter": "CO",
            "Unit": "PPM",
            "Value": 0.1,
            "RawConcentration": 0.1,
        }
    ]
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert state_by_unique_id(hass, "320030044-co").state == "0.1"
    assert state_by_unique_id(hass, "320030044-co_aqi").state == "unknown"
    assert state_by_unique_id(hass, "320030044-aqi").state == "unknown"


def test_concentration_attrs_none_when_param_missing(mock_api) -> None:
    """Attribute property guards against a parameter vanishing mid-query."""
    from unittest.mock import MagicMock

    from custom_components.airnow_station.sensor import (
        AirNowStationConcentrationSensor,
    )

    coordinator = MagicMock()
    coordinator.station_code = "320030044"
    coordinator.station_name = "Mountains Edge"
    coordinator.data = {
        "PM2.5": {"UTC": "2026-06-09T19:00", "Value": 3.3, "AgencyName": "Test"}
    }
    sensor = AirNowStationConcentrationSensor(coordinator, "PM2.5")
    coordinator.data = {}
    assert sensor.extra_state_attributes is None
    assert sensor.native_value is None
