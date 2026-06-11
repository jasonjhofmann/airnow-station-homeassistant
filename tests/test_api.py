"""Unit tests for the /aq/data/ client (no Home Assistant involved)."""

import asyncio
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from custom_components.airnow_station import api as api_module
from custom_components.airnow_station.api import (
    DATA_PARAMETERS,
    AirNowDataAPI,
    Data,
    latest_by_parameter,
)

START = datetime(2026, 6, 9, 7, 30)
END = datetime(2026, 6, 9, 19, 30)


async def test_bbox_builds_query() -> None:
    """bbox() formats dates, BBOX, and flags as the API expects."""
    request = AsyncMock(return_value=[])
    data = Data(request)

    result = await data.bbox(
        -115.27, 36.0, -115.25, 36.01, start_date=START, end_date=END
    )

    assert result == []
    endpoint = request.call_args.args[0]
    params = request.call_args.kwargs["params"]
    assert endpoint == "aq/data/"
    assert params["startDate"] == "2026-06-09T07"
    assert params["endDate"] == "2026-06-09T19"
    assert params["BBOX"] == "-115.27,36.0,-115.25,36.01"
    assert params["parameters"] == ",".join(DATA_PARAMETERS)
    assert params["dataType"] == "B"
    assert params["monitorType"] == "2"
    assert params["verbose"] == "1"
    assert params["includerawconcentrations"] == "0"


async def test_bbox_custom_arguments() -> None:
    """Non-default parameters/flags are passed through."""
    request = AsyncMock(return_value=[])
    data = Data(request)

    await data.bbox(
        -1.0,
        -2.0,
        1.0,
        2.0,
        start_date=START,
        end_date=END,
        parameters=("OZONE",),
        data_type="A",
        monitor_type=0,
        verbose=False,
        include_raw_concentrations=True,
    )

    params = request.call_args.kwargs["params"]
    assert params["parameters"] == "OZONE"
    assert params["dataType"] == "A"
    assert params["monitorType"] == "0"
    assert params["verbose"] == "0"
    assert params["includerawconcentrations"] == "1"


async def test_bbox_times_out_on_hung_request(monkeypatch) -> None:
    """A stalled request raises TimeoutError instead of hanging.

    With Home Assistant's injected session, pyairnow's own 10 s
    ClientTimeout does not apply; bbox() must enforce its own deadline.
    """

    async def hang(endpoint: str, **kwargs: Any) -> list[dict[str, Any]]:
        await asyncio.sleep(60)
        return []

    monkeypatch.setattr(api_module, "REQUEST_TIMEOUT", 0.05)
    data = Data(hang)
    with pytest.raises(TimeoutError):
        await data.bbox(-115.27, 36.0, -115.25, 36.01, start_date=START, end_date=END)


def test_airnow_data_api_wires_data_endpoint() -> None:
    """The WebServiceAPI subclass exposes the data endpoint."""
    client = AirNowDataAPI("test-key")
    assert isinstance(client.data, Data)
    assert client.data._request == client._get


def test_latest_by_parameter_edge_cases() -> None:
    """Sentinel/null/missing Values are skipped; latest wins."""
    rows = [
        {"Parameter": "OZONE", "UTC": "2026-06-09T18:00", "Value": 50.0, "AQI": 46},
        {"Parameter": "OZONE", "UTC": "2026-06-09T19:00", "Value": 49.0, "AQI": 45},
        {"Parameter": "OZONE", "UTC": "2026-06-09T20:00", "Value": -999.0, "AQI": -999},
        {"Parameter": "PM2.5", "UTC": "2026-06-09T19:00"},  # no Value key
        # JSON null Value must be skipped, not crash float() downstream.
        {"Parameter": "PM10", "UTC": "2026-06-09T20:00", "Value": None, "AQI": None},
        {"Parameter": "PM10", "UTC": "2026-06-09T19:00", "Value": 18.0, "AQI": 17},
    ]
    latest = latest_by_parameter(rows)
    assert set(latest) == {"OZONE", "PM10"}
    assert latest["OZONE"]["UTC"] == "2026-06-09T19:00"
    assert latest["PM10"]["UTC"] == "2026-06-09T19:00"


def test_latest_by_parameter_normalizes_missing_aqi() -> None:
    """Rows lacking AQI (or with null AQI) get the -999 sentinel."""
    rows = [
        {"Parameter": "CO", "UTC": "2026-06-09T19:00", "Value": 0.1},
        {"Parameter": "OZONE", "UTC": "2026-06-09T19:00", "Value": 49.0, "AQI": None},
        {"Parameter": "PM2.5", "UTC": "2026-06-09T19:00", "Value": 3.3, "AQI": 18},
    ]
    latest = latest_by_parameter(rows)
    assert latest["CO"]["AQI"] == -999.0
    assert latest["OZONE"]["AQI"] == -999.0
    assert latest["PM2.5"]["AQI"] == 18
