# AirNow Station

[![GitHub release](https://img.shields.io/github/v/release/jasonjhofmann/airnow-station?include_prereleases)](https://github.com/jasonjhofmann/airnow-station/releases)
[![Validate](https://github.com/jasonjhofmann/airnow-station/actions/workflows/validate.yml/badge.svg)](https://github.com/jasonjhofmann/airnow-station/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License](https://img.shields.io/github/license/jasonjhofmann/airnow-station)](LICENSE)

Home Assistant integration for a **single AirNow monitoring station**, using
the AirNow [query data (`/aq/data/`)](https://docs.airnowapi.org/Data/docs)
endpoint.

## Why not the core AirNow integration?

The core [`airnow`](https://www.home-assistant.io/integrations/airnow/)
integration uses AirNow's *observation* endpoints, which aggregate monitors
into a **reporting area** (e.g. "Las Vegas") and back-compute concentrations
from the area AQI. If you care about the monitor down the street — say,
Clark County DES's *Mountains Edge* station rather than the valley-wide
roll-up — that data never appears there.

This integration instead queries `/aq/data/` with a tight bounding box around
one station, giving you that monitor's actual hourly **measured
concentrations** plus per-pollutant **AQI**.

## Installation

Until this repo is in the HACS default store, add it as a custom repository:

1. HACS → ⋮ → *Custom repositories* → add
   `https://github.com/jasonjhofmann/airnow-station` (type: Integration).
2. Install **AirNow Station** and restart Home Assistant.

## Configuration

Settings → Devices & Services → Add Integration → **AirNow Station**.

You need a free [AirNow API key](https://docs.airnowapi.org/account/request/).
Enter the key and coordinates; every station that reported data within
~25 km in the last 3 hours is listed with its distance — pick one. Repeat to
add more stations.

## Entities

One service device per station. Sensors are created only for the parameters
the station actually reports (of: ozone, PM2.5, PM10, NO₂, SO₂, CO):

| Entity | Unit | Notes |
| --- | --- | --- |
| Air quality index | AQI | Max across pollutants; attributes: dominant pollutant, category, observation time |
| `<pollutant>` | µg/m³ / ppb / ppm | Measured concentration; attributes: observation time, raw concentration |
| `<pollutant>` AQI | AQI | Per-pollutant AQI |

Data is hourly (polled every 15 minutes; AirNow publishes with some lag).
AirNow's `-999` missing-value sentinels are filtered out.

## Upstream plans

The `/aq/data/` client (`api.py`) is deliberately written in
[pyairnow](https://github.com/asymworks/pyairnow)'s house style, with no
Home Assistant imports, so it can be PRed upstream as `pyairnow.data`; a
station mode for the core integration could follow. `scripts/smoke_test.py`
exercises it standalone against the live API.

## Development

```sh
pip install -r requirements_test.txt
pytest tests
AIRNOW_API_KEY=... python3 scripts/smoke_test.py 36.002 -115.26
```

## Attribution

Data provided by [AirNow](https://www.airnow.gov/), a partnership of the
U.S. EPA and federal, state, local, and tribal air quality agencies. Use of
the data is subject to the
[AirNow data exchange guidelines](https://docs.airnowapi.org/docs/AirNowAPIFactSheet.pdf).
