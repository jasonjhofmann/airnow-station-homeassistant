#!/usr/bin/env python3
"""Standalone live smoke test for the /aq/data/ client.

Exercises api.py against the real AirNow API without Home Assistant —
also serves as the demo script for an eventual pyairnow PR.

Usage:
    AIRNOW_API_KEY=... python3 scripts/smoke_test.py [lat] [lon]
"""

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__), "..", "custom_components", "airnow_station"
    ),
)

from api import AirNowDataAPI, latest_by_parameter  # noqa: E402


async def main() -> None:
    api_key = os.environ.get("AIRNOW_API_KEY")
    if not api_key:
        sys.exit("Set AIRNOW_API_KEY")
    lat = float(sys.argv[1]) if len(sys.argv) > 2 else 36.002
    lon = float(sys.argv[2]) if len(sys.argv) > 2 else -115.26

    client = AirNowDataAPI(api_key)
    end = datetime.now(UTC)
    rows = await client.data.bbox(
        lon - 0.25,
        lat - 0.25,
        lon + 0.25,
        lat + 0.25,
        start_date=end - timedelta(hours=3),
        end_date=end,
        include_raw_concentrations=True,
    )
    stations: dict[str, list] = {}
    for row in rows:
        stations.setdefault(f"{row['SiteName']} ({row['FullAQSCode']})", []).append(row)

    print(f"{len(rows)} rows from {len(stations)} stations:\n")
    for name, station_rows in sorted(stations.items()):
        print(name)
        for param, row in sorted(latest_by_parameter(station_rows).items()):
            print(
                f"  {param:>6}: {row['Value']} {row['Unit']}"
                f"  AQI {row['AQI']}  @ {row['UTC']}Z"
            )


if __name__ == "__main__":
    asyncio.run(main())
