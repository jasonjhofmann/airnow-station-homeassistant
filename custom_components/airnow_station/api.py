"""Client for the AirNow ``/aq/data/`` (query data) endpoint.

The upstream ``pyairnow`` library only wraps the observation and forecast
endpoints, which aggregate to AirNow *reporting areas*. This module adds a
``Data`` class written in pyairnow's house style so it can be proposed
upstream (as ``pyairnow.data``) largely unchanged; ``Data`` accepts any
request callable, so upstream would simply wire it to ``WebServiceAPI._get``.

``AirNowDataAPI`` used to obtain that callable by subclassing
``WebServiceAPI`` and reaching into its private ``_get`` — coupling this
integration to the internals of whatever pyairnow version happens to be
installed. The installed version is shared with Home Assistant core's own
``airnow`` integration, and two integrations exact-pinning different
versions of one package uninstall each other's copy on every restart.
``AirNowDataAPI`` therefore owns an equivalent request layer (same params,
session ownership, and ``WebServiceError`` mapping as ``WebServiceAPI._get``)
and imports only pyairnow's public error classes, which are stable across
releases. That is what lets ``manifest.json`` declare a version *floor*
(``pyairnow>=1.3.1``) instead of an exact pin.

This module intentionally has no Home Assistant imports so it stays
importable standalone (see ``scripts/smoke_test.py``) and PR-ready.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine, Sequence
from datetime import datetime
from json import JSONDecodeError
from typing import Any, NoReturn

from aiohttp import ClientSession, ClientTimeout
from pyairnow.errors import (
    AirNowError,
    EmptyResponseError,
    InvalidJsonError,
    InvalidKeyError,
)

_LOGGER = logging.getLogger(__name__)

API_BASE_URL = "https://www.airnowapi.org"

# 10 s deadline on every request (pyairnow's intended default). With Home
# Assistant's injected shared session an aiohttp ClientTimeout set at session
# creation does not apply, so ``Data.bbox`` additionally enforces the same
# deadline with ``asyncio.timeout`` regardless of session ownership.
REQUEST_TIMEOUT = 10

# Identifiers accepted by the ``parameters`` query argument. Note the
# request spelling (``PM25``) differs from the response spelling (``PM2.5``).
DATA_PARAMETERS: tuple[str, ...] = ("OZONE", "PM25", "PM10", "CO", "NO2", "SO2")

# Sentinel AirNow uses for missing/not-yet-validated values.
MISSING_VALUE = -999.0


class Data:
    """Retrieve monitor-level (per-site) data by bounding box."""

    def __init__(
        self, request: Callable[..., Coroutine[Any, Any, list[dict[str, Any]]]]
    ) -> None:
        self._request = request

    async def bbox(
        self,
        min_longitude: float,
        min_latitude: float,
        max_longitude: float,
        max_latitude: float,
        *,
        start_date: datetime,
        end_date: datetime,
        parameters: Sequence[str] = DATA_PARAMETERS,
        data_type: str = "B",
        monitor_type: int = 2,
        verbose: bool = True,
        include_raw_concentrations: bool = False,
    ) -> list[dict[str, Any]]:
        """Request site-level data rows inside a bounding box.

        ``start_date``/``end_date`` must be timezone-naive UTC or
        UTC-aware datetimes; the API expects UTC hours.
        """
        params: dict[str, str] = {
            "startDate": start_date.strftime("%Y-%m-%dT%H"),
            "endDate": end_date.strftime("%Y-%m-%dT%H"),
            "parameters": ",".join(parameters),
            "BBOX": (f"{min_longitude},{min_latitude},{max_longitude},{max_latitude}"),
            "dataType": data_type,
            "monitorType": str(monitor_type),
            "verbose": str(int(verbose)),
            "includerawconcentrations": str(int(include_raw_concentrations)),
        }
        _LOGGER.debug("GET aq/data/ params=%s", params)  # API key not in params
        async with asyncio.timeout(REQUEST_TIMEOUT):
            return await self._request("aq/data/", params=params)


def _raise_web_service_error(ws_err: Any) -> NoReturn:
    """Map an API ``WebServiceError`` payload to a pyairnow exception.

    Mirrors ``WebServiceAPI._get`` exactly, including its exact-match
    message comparison — the live API currently appends a trailing period
    to "Request not authenticated.", which pyairnow (and therefore this
    mirror) classifies as a generic ``AirNowError``. Kept bug-for-bug so
    behavior is identical whichever pyairnow version is installed.
    """
    if isinstance(ws_err, list) and len(ws_err) > 0:
        first = ws_err[0]
        if isinstance(first, dict) and "Message" in first:
            message = first["Message"]
            if message in ("Invalid API key", "Request not authenticated"):
                raise InvalidKeyError(message)
            raise AirNowError(message)
        raise AirNowError(str(first))
    raise AirNowError(str(ws_err))


class AirNowDataAPI:
    """Standalone client wiring ``Data`` to the AirNow web API.

    The request layer replicates the contract of pyairnow's
    ``WebServiceAPI._get`` — auth/format query params, injected-session
    reuse with a self-owned fallback session, and ``WebServiceError``
    mapping onto pyairnow's public exception classes — without depending
    on that private method.
    """

    def __init__(self, api_key: str, *, session: ClientSession | None = None) -> None:
        self._api_key = api_key
        self._session = session
        self.data = Data(self._get)

    async def _get(
        self, endpoint: str, *, base_url: str = API_BASE_URL, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Run an authenticated GET against the API (pyairnow semantics)."""
        params: dict[str, str] = kwargs.setdefault("params", {})
        params["API_KEY"] = self._api_key
        params["format"] = "application/json"

        session = self._session
        if owns_session := session is None or session.closed:
            session = ClientSession(timeout=ClientTimeout(total=REQUEST_TIMEOUT))

        try:
            async with session.get(f"{base_url}/{endpoint}", **kwargs) as resp:
                try:
                    data = await resp.json(content_type=None)
                except JSONDecodeError as err:
                    # The response is not JSON; surface its body text.
                    raise InvalidJsonError(await resp.text()) from err
        finally:
            if owns_session:
                await session.close()

        if isinstance(data, dict) and "WebServiceError" in data:
            _raise_web_service_error(data["WebServiceError"])
        if not isinstance(data, list):
            # We should get a list of data rows.
            raise InvalidJsonError(f"Unexpected response type: {type(data)}")
        if len(data) == 0:
            raise EmptyResponseError("No data was returned")
        return data


def latest_by_parameter(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Reduce raw data rows to the most recent valid row per parameter.

    Rows whose ``Value`` is missing, ``null``, or the -999 sentinel are
    ignored (a JSON ``null`` would otherwise slip past the sentinel check
    and crash ``float(row["Value"])`` downstream). A missing or ``null``
    ``AQI`` is normalized to the sentinel so consumers can rely on the key
    and treat it exactly like the API's "no AQI computed" rows. ``UTC``
    strings are fixed-width ISO timestamps, so lexicographic comparison
    is safe.
    """
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row.get("Value")
        if value is None or value == MISSING_VALUE:
            continue
        param = row["Parameter"]
        if param not in latest or row["UTC"] > latest[param]["UTC"]:
            if row.get("AQI") is None:
                row = {**row, "AQI": MISSING_VALUE}
            latest[param] = row
    return latest
