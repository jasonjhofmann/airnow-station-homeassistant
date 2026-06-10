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
prompts for reauthentication automatically; to rotate the key
proactively, use the **Reconfigure** flow instead: Settings → Devices &
Services → AirNow Station → ⋮ (on the account entry) → Reconfigure.
The new key is validated against the API before being saved and all
stations on the account switch to it immediately.

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

### Entity attributes

| Entity | Attribute | Meaning |
| --- | --- | --- |
| Concentrations | `observed_utc` | UTC hour of the observation shown |
| Concentrations | `raw_concentration` | Unvalidated instrument value (omitted while AirNow reports the `-999` placeholder) |
| Air quality index | `dominant_pollutant` | Parameter responsible for the overall AQI |
| Air quality index | `category` | EPA category name (Good … Hazardous) |
| Air quality index | `observed_utc` | UTC hour of the dominant observation |

## Supported stations

Any monitoring station that reports to AirNow's `/aq/data/` feed — in
practice, US EPA AQS stations operated by state/county/tribal agencies,
plus US embassies abroad. If a station appears on the
[AirNow map](https://gispub.epa.gov/airnow/) it should be discoverable
here. Stations report different parameter sets (many are ozone+PM only;
near-road stations are typically NO₂/CO only); sensors are created for
whatever the station actually reports.

## Examples

Notify when ozone at your station crosses a threshold:

```yaml
automation:
  - alias: "Ozone advisory"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.my_station_ozone
        above: 55
        for: "00:15:00"
    actions:
      - action: notify.mobile_app_my_phone
        data:
          title: "Ozone {{ states('sensor.my_station_ozone') }} ppb"
          message: "Above 55 ppb at the monitoring station — consider closing up."
```

Template binary sensor for "any pollutant unhealthy" using the overall AQI:

```yaml
template:
  - binary_sensor:
      - name: "Outdoor air unhealthy"
        state: "{{ states('sensor.my_station_air_quality_index') | int(0) > 100 }}"
        attributes:
          dominant: "{{ state_attr('sensor.my_station_air_quality_index', 'dominant_pollutant') }}"
```

## Known limitations

- **Hourly data with publication lag.** AirNow publishes hourly; a new
  hour's values typically appear 30–90 minutes after the hour. The
  integration polls every 15 minutes and always shows the latest
  *validated* row (AirNow's `-999` placeholders are skipped).
- **CO often has no AQI.** Stations report CO concentrations, but AirNow
  frequently returns `-999` for its AQI at ambient levels — the CO AQI
  sensor then reads `unknown`. This is upstream behavior.
- **ppb pollutants carry no device class.** Home Assistant's ozone/NO₂/SO₂
  device classes require µg/m³; AirNow reports ppb, so those sensors have
  units but no device class.
- **Parameter sets can change.** If a station starts reporting a new
  pollutant, reload the integration (or restart) to create its sensors.
- **Rate limits.** AirNow keys default to 500 requests/hour; this
  integration uses 4/hour per station.

## Troubleshooting

- **"Invalid authentication" during setup** — the API key is wrong or not
  yet activated (AirNow keys can take a few minutes after signup).
- **"No stations reported data near these coordinates"** — widen your
  search by entering coordinates closer to a metro area; rural coverage
  is sparse. Stations that haven't reported in the last 3 hours won't
  appear.
- **Entities `unavailable`** — the station missed its last publications
  (maintenance and data outages are common); check the station on the
  [AirNow map](https://gispub.epa.gov/airnow/). The integration recovers
  automatically when data resumes. A station that is already down when
  Home Assistant starts loads without sensors and creates them
  automatically on recovery; other stations on the account are
  unaffected either way.
- **Re-auth prompt appears** — the key was revoked or rate-limited;
  enter a valid key, or wait out the rate-limit window.
- **Download diagnostics** (integration page → ⋮ → Download diagnostics)
  to see exactly what the station last reported, the update health, and the
  last error — the API key is redacted.
- **Enable debug logging** (integration page → ⋮ → Enable debug logging, or
  `logger:` → `custom_components.airnow_station: debug`) to see each poll's
  window, row counts, and the latest timestamp per parameter.

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

See [CONTRIBUTING.md](CONTRIBUTING.md) — architecture tour, dev setup,
quality gates (pytest+coverage, mypy strict, ruff), and the release process.

```sh
pip install -r requirements_test.txt
pytest tests -q --cov=custom_components.airnow_station
AIRNOW_API_KEY=... python3 scripts/smoke_test.py 36.1 -115.2
```

## Attribution

Data provided by [AirNow](https://www.airnow.gov/), a partnership of the
U.S. EPA and federal, state, local, and tribal air quality agencies. Use of
the data is subject to the
[AirNow data exchange guidelines](https://docs.airnowapi.org/docs/AirNowAPIFactSheet.pdf).
