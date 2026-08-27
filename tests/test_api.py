"""Unit tests for the /aq/data/ client (no Home Assistant involved)."""

import asyncio
from datetime import datetime
from json import JSONDecodeError
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pyairnow.errors import (
    AirNowError,
    EmptyResponseError,
    InvalidJsonError,
    InvalidKeyError,
)

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
    """The client exposes the data endpoint bound to its own request layer."""
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


class _FakeResponse:
    """Minimal stand-in for an aiohttp response context manager."""

    def __init__(
        self,
        payload: Any = None,
        *,
        body_text: str = "",
        json_error: bool = False,
    ) -> None:
        self._payload = payload
        self._body_text = body_text
        self._json_error = json_error

    async def json(self, content_type: str | None = None) -> Any:
        if self._json_error:
            raise JSONDecodeError("not json", self._body_text or "x", 0)
        return self._payload

    async def text(self) -> str:
        return self._body_text

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None


class _FakeSession:
    """Just enough of aiohttp.ClientSession for AirNowDataAPI._get."""

    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.closed = False
        self.get_calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.get_calls.append((url, kwargs))
        return self._response

    async def close(self) -> None:
        self.closed = True


async def test_get_injects_auth_and_format_params() -> None:
    """_get adds API_KEY/format to the caller's params and returns the rows."""
    session = _FakeSession(_FakeResponse([{"Parameter": "OZONE"}]))
    client = AirNowDataAPI("test-key", session=session)  # type: ignore[arg-type]

    rows = await client._get("aq/data/", params={"BBOX": "1,2,3,4"})

    assert rows == [{"Parameter": "OZONE"}]
    url, kwargs = session.get_calls[0]
    assert url == "https://www.airnowapi.org/aq/data/"
    assert kwargs["params"]["API_KEY"] == "test-key"
    assert kwargs["params"]["format"] == "application/json"
    assert kwargs["params"]["BBOX"] == "1,2,3,4"
    assert not session.closed  # injected session is left open


@pytest.mark.parametrize("message", ["Invalid API key", "Request not authenticated"])
async def test_get_maps_auth_errors(message: str) -> None:
    """Auth-related WebServiceError messages raise InvalidKeyError."""
    session = _FakeSession(_FakeResponse({"WebServiceError": [{"Message": message}]}))
    client = AirNowDataAPI("bad-key", session=session)  # type: ignore[arg-type]

    with pytest.raises(InvalidKeyError, match=message):
        await client._get("aq/data/")


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ({"WebServiceError": [{"Message": "Rate limit exceeded"}]}, "Rate limit"),
        ({"WebServiceError": [["no Message key"]]}, "no Message key"),
        ({"WebServiceError": "catastrophe"}, "catastrophe"),
        ({"WebServiceError": []}, r"\[\]"),
    ],
)
async def test_get_maps_other_web_service_errors(payload: Any, match: str) -> None:
    """Non-auth WebServiceError payload shapes all raise AirNowError."""
    session = _FakeSession(_FakeResponse(payload))
    client = AirNowDataAPI("key", session=session)  # type: ignore[arg-type]

    with pytest.raises(AirNowError, match=match):
        await client._get("aq/data/")


async def test_get_rejects_non_list_json() -> None:
    """A JSON body that is not a list raises InvalidJsonError."""
    session = _FakeSession(_FakeResponse({"unexpected": True}))
    client = AirNowDataAPI("key", session=session)  # type: ignore[arg-type]

    with pytest.raises(InvalidJsonError, match="Unexpected response type"):
        await client._get("aq/data/")


async def test_get_rejects_empty_list() -> None:
    """An empty list raises EmptyResponseError (matching pyairnow)."""
    session = _FakeSession(_FakeResponse([]))
    client = AirNowDataAPI("key", session=session)  # type: ignore[arg-type]

    with pytest.raises(EmptyResponseError):
        await client._get("aq/data/")


async def test_get_invalid_json_surfaces_body_text() -> None:
    """A non-JSON body raises InvalidJsonError carrying the response text."""
    session = _FakeSession(
        _FakeResponse(json_error=True, body_text="<html>maintenance</html>")
    )
    client = AirNowDataAPI("key", session=session)  # type: ignore[arg-type]

    with pytest.raises(InvalidJsonError, match="maintenance"):
        await client._get("aq/data/")


async def test_get_creates_and_closes_own_session(monkeypatch) -> None:
    """Without an injected session, _get creates one with the 10 s timeout
    (pyairnow's default applies only to sessions it owns) and closes it."""
    session = _FakeSession(_FakeResponse([{"ok": 1}]))
    created: list[Any] = []

    def factory(*, timeout: Any) -> _FakeSession:
        created.append(timeout)
        return session

    monkeypatch.setattr(api_module, "ClientSession", factory)
    client = AirNowDataAPI("key")  # no session injected

    rows = await client._get("aq/data/")

    assert rows == [{"ok": 1}]
    assert session.closed
    assert created[0].total == api_module.REQUEST_TIMEOUT


async def test_get_replaces_closed_injected_session(monkeypatch) -> None:
    """A closed injected session is not reused; a self-owned one substitutes."""
    stale = _FakeSession(_FakeResponse([]))
    stale.closed = True
    fresh = _FakeSession(_FakeResponse([{"ok": 1}]))
    monkeypatch.setattr(api_module, "ClientSession", lambda *, timeout: fresh)
    client = AirNowDataAPI("key", session=stale)  # type: ignore[arg-type]

    rows = await client._get("aq/data/")

    assert rows == [{"ok": 1}]
    assert not stale.get_calls  # the stale session was never used
    assert fresh.closed  # the substitute is owned, so it is closed


async def test_get_closes_own_session_on_error_payload() -> None:
    """The owned-session cleanup runs before error payloads are mapped."""
    session = _FakeSession(
        _FakeResponse({"WebServiceError": [{"Message": "Invalid API key"}]})
    )
    client = AirNowDataAPI("bad-key")
    client._session = None  # explicit: no injected session

    def factory(*, timeout: Any) -> _FakeSession:
        return session

    original = api_module.ClientSession
    api_module.ClientSession = factory  # type: ignore[assignment]
    try:
        with pytest.raises(InvalidKeyError):
            await client._get("aq/data/")
    finally:
        api_module.ClientSession = original  # type: ignore[assignment]

    assert session.closed
