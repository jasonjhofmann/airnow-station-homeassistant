"""Tests for integration setup, unload, and coordinator failure modes."""

from pyairnow.errors import AirNowError, EmptyResponseError, InvalidKeyError
import pytest

from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.core import HomeAssistant

from custom_components.airnow_station.const import DOMAIN

from .conftest import OTHER_STATION, SAMPLE_ROWS, make_account_entry


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


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (InvalidKeyError("Invalid API key"), ConfigEntryState.SETUP_ERROR),
        (EmptyResponseError("No data was returned"), ConfigEntryState.SETUP_RETRY),
        (AirNowError("boom"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_failures(
    hass: HomeAssistant, mock_api, side_effect, expected_state
) -> None:
    """Auth failures hard-fail; transient API failures retry."""
    mock_api.data.bbox.side_effect = side_effect
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is expected_state


async def test_setup_retries_when_station_has_no_rows(
    hass: HomeAssistant, mock_api
) -> None:
    """Rows for other stations only -> no data for ours -> retry."""
    mock_api.data.bbox.return_value = [
        row for row in SAMPLE_ROWS if row["FullAQSCode"] == OTHER_STATION["FullAQSCode"]
    ]
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
