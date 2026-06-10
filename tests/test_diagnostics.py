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


def test_redact_set_covers_raw_request_keys() -> None:
    """Future-proofing: the raw AirNow query-param casing scrubs if a
    future revision attaches request context; public station metadata
    deliberately survives."""
    from homeassistant.components.diagnostics import async_redact_data

    from custom_components.airnow_station.diagnostics import TO_REDACT

    hypothetical = {
        "api_key": "secret",
        "request": {
            "params": {"API_KEY": "secret", "BBOX": "-115.27,36.0,-115.25,36.01"}
        },
        "Latitude": 36.0075,  # public EPA monitor metadata: kept
        "FullAQSCode": "320030044",
    }
    out = async_redact_data(hypothetical, TO_REDACT)
    assert out["api_key"] == "**REDACTED**"
    assert out["request"]["params"]["API_KEY"] == "**REDACTED**"
    assert out["request"]["params"]["BBOX"] == "-115.27,36.0,-115.25,36.01"
    assert out["Latitude"] == 36.0075
    assert out["FullAQSCode"] == "320030044"
