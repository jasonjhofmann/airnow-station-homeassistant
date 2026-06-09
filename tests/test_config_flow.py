"""Tests for the AirNow Station config flow."""

from pyairnow.errors import EmptyResponseError, InvalidKeyError
import pytest

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airnow_station.const import (
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    DOMAIN,
)

USER_INPUT = {
    CONF_API_KEY: "test-key",
    CONF_LATITUDE: 36.002,
    CONF_LONGITUDE: -115.26,
}


async def test_full_flow(hass: HomeAssistant, mock_api) -> None:
    """Happy path: discover stations, pick one, create the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "station"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"station": "320030044"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Mountains Edge"
    assert result["data"] == {
        CONF_API_KEY: "test-key",
        CONF_STATION_CODE: "320030044",
        CONF_STATION_NAME: "Mountains Edge",
        CONF_LATITUDE: 36.0075,
        CONF_LONGITUDE: -115.263056,
    }
    assert result["result"].unique_id == "320030044"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (InvalidKeyError("Invalid API key"), "invalid_auth"),
        (EmptyResponseError("No data was returned"), "no_stations"),
    ],
)
async def test_user_step_errors(
    hass: HomeAssistant, mock_api, side_effect, error
) -> None:
    """Errors surface on the user step, then the flow recovers."""
    mock_api.data.bbox.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_api.data.bbox.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["step_id"] == "station"


async def test_duplicate_station_aborts(hass: HomeAssistant, mock_api) -> None:
    """Configuring an already-configured station aborts."""
    MockConfigEntry(domain=DOMAIN, unique_id="320030044").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"station": "320030044"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
