"""Client for the AirNow ``/aq/data/`` (query data) endpoint.

The upstream ``pyairnow`` library only wraps the observation and forecast
endpoints, which aggregate to AirNow *reporting areas*. This module adds a
``Data`` class written in pyairnow's house style so it can be proposed
upstream (as ``pyairnow.data``) largely unchanged; ``AirNowDataAPI`` mirrors
how ``WebServiceAPI`` would wire it in.

This module intentionally has no Home Assistant imports so it stays
importable standalone (see ``scripts/smoke_test.py``) and PR-ready.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine, Sequence
from datetime import datetime
from typing import Any

from pyairnow.api import WebServiceAPI

_LOGGER = logging.getLogger(__name__)

# pyairnow's 10 s ClientTimeout only applies to sessions it creates
# itself; with an injected session (as Home Assistant injects its shared
# one) requests would otherwise run under aiohttp's 300 s default.
# Enforce the same 10 s here regardless of session ownership.
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


class AirNowDataAPI(WebServiceAPI):
    """``WebServiceAPI`` extended with the query-data endpoint."""

    def __init__(self, api_key: str, *, session: Any = None) -> None:
        super().__init__(api_key, session=session)
        self.data = Data(self._get)


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
