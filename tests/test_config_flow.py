"""Tests for the AirNow Station config and subentry flows."""

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pyairnow.errors import AirNowError, EmptyResponseError, InvalidKeyError

from custom_components.airnow_station.const import (
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    DOMAIN,
    SUBENTRY_TYPE_STATION,
)

from .conftest import make_account_entry

SEARCH_INPUT = {CONF_LATITUDE: 36.002, CONF_LONGITUDE: -115.26}


async def test_account_flow(hass: HomeAssistant, mock_api) -> None:
    """Happy path: validate the key and create the account entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-key"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AirNow"
    assert result["data"] == {CONF_API_KEY: "test-key"}
    assert result["result"].subentries == {}


async def test_account_flow_empty_area_still_validates(
    hass: HomeAssistant, mock_api
) -> None:
    """An empty discovery result proves the key works: entry is created."""
    mock_api.data.bbox.side_effect = EmptyResponseError("No data was returned")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-key"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_account_flow_invalid_auth(hass: HomeAssistant, mock_api) -> None:
    """A rejected key surfaces an error, then the flow recovers."""
    mock_api.data.bbox.side_effect = InvalidKeyError("Invalid API key")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "bad-key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_api.data.bbox.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-key"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_account_duplicate_aborts(hass: HomeAssistant, mock_api) -> None:
    """A second account entry with the same API key aborts."""
    make_account_entry(subentries=False).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-key"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_station_subentry_flow(hass: HomeAssistant, mock_api) -> None:
    """Add a station subentry to an account entry."""
    entry = make_account_entry(subentries=False)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_STATION), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], SEARCH_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "station"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"station": "320030044"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert len(entry.subentries) == 1
    subentry = next(iter(entry.subentries.values()))
    assert subentry.subentry_type == SUBENTRY_TYPE_STATION
    assert subentry.title == "Mountains Edge"
    assert subentry.unique_id == "320030044"
    assert subentry.data == {
        CONF_STATION_CODE: "320030044",
        CONF_STATION_NAME: "Mountains Edge",
        CONF_LATITUDE: 36.0075,
        CONF_LONGITUDE: -115.263056,
    }


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (InvalidKeyError("Invalid API key"), "invalid_auth"),
        (EmptyResponseError("No data was returned"), "no_stations"),
    ],
)
async def test_station_subentry_errors(
    hass: HomeAssistant, mock_api, side_effect, error
) -> None:
    """Errors surface on the search step, then the flow recovers."""
    entry = make_account_entry(subentries=False)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_api.data.bbox.side_effect = side_effect
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_STATION), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], SEARCH_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_api.data.bbox.side_effect = None
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], SEARCH_INPUT
    )
    assert result["step_id"] == "station"


async def test_duplicate_station_subentry_aborts(hass: HomeAssistant, mock_api) -> None:
    """Adding an already-configured station aborts."""
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_STATION), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], SEARCH_INPUT
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"station": "320030044"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(entry.subentries) == 1


async def test_reauth_flow(hass: HomeAssistant, mock_api) -> None:
    """Reauth rejects a bad key, then accepts a good one."""
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_api.data.bbox.side_effect = InvalidKeyError("Invalid API key")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "bad-key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_api.data.bbox.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-key"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "new-key"
    # The abort schedules a reload; let it settle, then unload so the
    # coordinator's refresh timer doesn't linger past the test.
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(entry.entry_id)


async def test_reauth_empty_response_is_valid(hass: HomeAssistant, mock_api) -> None:
    """An empty discovery result during reauth still proves the key works."""
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    mock_api.data.bbox.side_effect = EmptyResponseError("No data was returned")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-key"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "new-key"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (AirNowError("api down"), "cannot_connect"),
        (RuntimeError("surprise"), "unknown"),
    ],
)
async def test_account_flow_connection_errors(
    hass: HomeAssistant, mock_api, side_effect, error
) -> None:
    """API/unexpected errors surface on the account step."""
    mock_api.data.bbox.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (AirNowError("api down"), "cannot_connect"),
        (RuntimeError("surprise"), "unknown"),
    ],
)
async def test_station_subentry_connection_errors(
    hass: HomeAssistant, mock_api, side_effect, error
) -> None:
    """API/unexpected errors surface on the subentry search step."""
    entry = make_account_entry(subentries=False)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_api.data.bbox.side_effect = side_effect
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_STATION), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], SEARCH_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_station_subentry_rows_without_codes(
    hass: HomeAssistant, mock_api
) -> None:
    """Rows lacking FullAQSCode produce no stations -> no_stations error."""
    entry = make_account_entry(subentries=False)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_api.data.bbox.return_value = [
        {"Latitude": 36.0, "Longitude": -115.2, "Parameter": "OZONE", "Value": 40.0}
    ]
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_STATION), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], SEARCH_INPUT
    )
    assert result["errors"] == {"base": "no_stations"}


async def test_reauth_cannot_connect(hass: HomeAssistant, mock_api) -> None:
    """Connection errors during reauth keep the form open."""
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    mock_api.data.bbox.side_effect = AirNowError("api down")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow(hass: HomeAssistant, mock_api) -> None:
    """Reconfigure validates and updates the API key."""
    entry = make_account_entry(subentries=True)
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_api.data.bbox.side_effect = InvalidKeyError("Invalid API key")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "bad-key"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    mock_api.data.bbox.side_effect = AirNowError("api down")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-key"}
    )
    assert result["errors"] == {"base": "cannot_connect"}

    mock_api.data.bbox.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-key"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_API_KEY] == "new-key"
    # The abort schedules a reload; let it settle, then unload so the
    # coordinator's refresh timer doesn't linger past the test.
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(entry.entry_id)
