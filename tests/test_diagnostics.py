"""Tests for diagnostics."""

from homeassistant.core import HomeAssistant

from custom_components.airnow_station.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import make_account_entry


async def test_diagnostics_redacts_api_key(hass: HomeAssistant, mock_api) -> None:
    """Diagnostics include station data with the API key redacted."""
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["entry_data"]["api_key"] == "**REDACTED**"
    assert len(diag["stations"]) == 1
    station = diag["stations"][0]
    assert station["subentry"]["station_code"] == "320030044"
    assert station["last_update_success"] is True
    assert "OZONE" in station["data"]
