"""Tests for integration setup, unload, and coordinator failure modes."""

from datetime import timedelta

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util
from pyairnow.errors import AirNowError, EmptyResponseError, InvalidKeyError
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.airnow_station.const import DEFAULT_UPDATE_INTERVAL, DOMAIN

from .conftest import (
    OTHER_STATION,
    SAMPLE_ROWS,
    SILENT_STATION_SUBENTRY,
    make_account_entry,
)


async def test_setup_and_unload(hass: HomeAssistant, mock_api) -> None:
    """Entry sets up with a station and unloads cleanly."""
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_non_station_subentries_are_skipped(
    hass: HomeAssistant, mock_api
) -> None:
    """Subentries of unknown types do not get coordinators."""
    entry = make_account_entry(subentries=True, foreign_subentry=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert len(entry.runtime_data) == 1  # only the station subentry


async def test_setup_auth_failure_fails_entry(hass: HomeAssistant, mock_api) -> None:
    """Every station rejecting the key hard-fails the entry; reauth fires."""
    mock_api.data.bbox.side_effect = InvalidKeyError("Invalid API key")
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


@pytest.mark.parametrize(
    "side_effect",
    [
        EmptyResponseError("No data was returned"),
        AirNowError("boom"),
        TimeoutError(),
    ],
)
async def test_setup_survives_station_outage(
    hass: HomeAssistant, mock_api, side_effect
) -> None:
    """Transient API failures degrade the station; the entry still loads."""
    mock_api.data.bbox.side_effect = side_effect
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    coordinator = next(iter(entry.runtime_data.values()))
    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, UpdateFailed)
    # No reported parameters -> no entities yet.
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, "320030044-aqi") is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_degrades_when_station_has_no_rows(
    hass: HomeAssistant, mock_api
) -> None:
    """Rows for other stations only -> ours degrades but the entry loads."""
    mock_api.data.bbox.return_value = [
        row for row in SAMPLE_ROWS if row["FullAQSCode"] == OTHER_STATION["FullAQSCode"]
    ]
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    coordinator = next(iter(entry.runtime_data.values()))
    assert not coordinator.last_update_success

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_one_station_outage_keeps_others_alive(
    hass: HomeAssistant, mock_api
) -> None:
    """A station with no data degrades alone; the healthy station works."""
    entry = make_account_entry(
        subentries=True, extra_subentries=[SILENT_STATION_SUBENTRY]
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert len(entry.runtime_data) == 2

    # The healthy station's entities exist and report data.
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, "320030044-ozone")
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "49.0"

    # The silent station produced no entities (nothing to build them from).
    assert registry.async_get_entity_id("sensor", DOMAIN, "060371234-aqi") is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_station_recovery_reloads_entry(hass: HomeAssistant, mock_api) -> None:
    """A station down at setup gets its entities once data resumes."""
    mock_api.data.bbox.return_value = []
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, "320030044-aqi") is None

    # Data resumes; the next scheduled poll triggers a reload.
    mock_api.data.bbox.return_value = SAMPLE_ROWS
    async_fire_time_changed(
        hass, dt_util.utcnow() + DEFAULT_UPDATE_INTERVAL + timedelta(seconds=30)
    )
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, "320030044-ozone")
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "49.0"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
