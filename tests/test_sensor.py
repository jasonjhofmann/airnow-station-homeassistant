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
