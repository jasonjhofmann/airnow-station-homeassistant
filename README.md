# AirNow Station

[![GitHub release](https://img.shields.io/github/v/release/jasonjhofmann/airnow-station-homeassistant?include_prereleases)](https://github.com/jasonjhofmann/airnow-station-homeassistant/releases)
[![Validate](https://github.com/jasonjhofmann/airnow-station-homeassistant/actions/workflows/validate.yml/badge.svg)](https://github.com/jasonjhofmann/airnow-station-homeassistant/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License](https://img.shields.io/github/license/jasonjhofmann/airnow-station-homeassistant)](LICENSE)

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
   `https://github.com/jasonjhofmann/airnow-station-homeassistant` (type: Integration).
2. Install **AirNow Station** and restart Home Assistant.

## Configuration

Settings → Devices & Services → Add Integration → **AirNow Station**.

You need a free [AirNow API key](https://docs.airnowapi.org/account/request/).
The key is entered **once**, creating an account entry. Stations are then
added to that account as subentries: open the AirNow Station card and choose
**Add monitoring station**, enter coordinates, and every station that
reported data within ~25 km in the last 3 hours is listed with its
distance — pick one. Repeat for as many stations as you like; duplicates
are rejected by AQS code.

### Parameters

| Step | Parameter | Description |
| --- | --- | --- |
| Account | API key | Your AirNow API key (free; rate limit 500 requests/hour, this integration uses 4/hour per station) |
| Add monitoring station | Latitude / Longitude | Center of the station search (defaults to your Home Assistant home location) |
| Add monitoring station | Monitoring station | Pick from stations that reported data within ~25 km in the last 3 hours |

### Options

The integration has no options flow. Polling is fixed at 15 minutes
(AirNow publishes hourly). If the API key is rejected, Home Assistant
prompts for reauthentication automatically; to change it proactively,
re-enter it through that same reauth prompt (Settings → Devices &
Services → AirNow Station → Reconfigure is planned but not yet
implemented — see quality_scale.yaml).

## Entities

One service device per station (each tied to its subentry, so removing a
station cleans up its device and entities). Sensors are created only for
the parameters the station actually reports (of: ozone, PM2.5, PM10, NO₂,
SO₂, CO):

| Entity | Unit | Notes |
| --- | --- | --- |
| Air quality index | AQI | Max across pollutants; attributes: dominant pollutant, category, observation time |
| `<pollutant>` | µg/m³ / ppb / ppm | Measured concentration; attributes: observation time, raw concentration |
| `<pollutant>` AQI | AQI | Per-pollutant AQI |

Data is hourly (polled every 15 minutes; AirNow publishes with some lag).
AirNow's `-999` missing-value sentinels are filtered out.

## Removal

1. To remove a single station: Settings → Devices & Services → **AirNow Station** → open the account entry, then delete that station's subentry (its device and entities are removed automatically).
2. To remove the integration entirely: delete the **AirNow Station** entry from Settings → Devices & Services, then uninstall the integration from HACS and restart Home Assistant.
3. Optionally revoke the AirNow API key from your [AirNow account](https://docs.airnowapi.org/) if nothing else uses it.

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
