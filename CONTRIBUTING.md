# Contributing

## Architecture (5-minute tour)

```
custom_components/airnow_station/
  api.py           /aq/data/ client in pyairnow house style. NO Home Assistant
                   imports — it is intended for an eventual upstream PR to
                   pyairnow and is testable standalone (see scripts/smoke_test.py).
  config_flow.py   Account flow (API key) + station subentry flow (coordinate
                   search → pick from discovered stations) + reauth + reconfigure.
  coordinator.py   One DataUpdateCoordinator per station subentry. Polls a tight
                   bounding box (±0.002°) around the station every 15 minutes,
                   filters rows by AQS code, reduces to the latest valid row per
                   parameter (-999 sentinels skipped).
  entity.py        Base entity: device-per-station wiring.
  sensor.py        Per-parameter concentration + AQI sensors, overall AQI.
  diagnostics.py   Config-entry diagnostics (API key redacted).
  brand/           Brand assets — generated, do not hand-edit; see scripts/.
  quality_scale.yaml  Self-assessment vs the core integration quality scale.
                   Keep statuses in sync with code changes.
```

Key invariants:

- **A station IS its AQS code** (the subentry unique ID). There is deliberately
  no station reconfigure — switching stations is remove + add.
- **`api.py` stays free of Home Assistant imports.**
- **`strings.json` and `translations/en.json` are kept identical** (copy on
  every change).
- Entities are added with `config_subentry_id` so HA cleans up devices and
  entities when a station subentry is removed.

## Development setup

```sh
uv venv .venv && uv pip install -p .venv/bin/python -r requirements_test.txt
.venv/bin/python -m pytest tests -q --cov=custom_components.airnow_station   # 100% expected
.venv/bin/python -m mypy --strict custom_components/airnow_station/
.venv/bin/python -m ruff check custom_components tests scripts
```

CI enforces all three (coverage ≥95%, mypy strict, ruff) plus hassfest and
HACS validation. Live smoke test against the real API (needs a free key):

```sh
AIRNOW_API_KEY=... python3 scripts/smoke_test.py 36.1 -115.2
```

Brand assets regenerate with `python3 scripts/generate_brand.py` (Pillow).

## Making a release

1. Update `CHANGELOG.md` and bump `version` in `manifest.json` (manifest keys
   must stay sorted: `domain`, `name`, then alphabetical — hassfest enforces).
2. Commit, push, and wait for the Validate workflow to go **green**.
3. Tag and create the GitHub release **after** the green run (HACS submission
   rules require the release to post-date passing validation).

## Debugging

Enable debug logging from the integration page (⋮ → Enable debug logging) or:

```yaml
logger:
  logs:
    custom_components.airnow_station: debug
    pyairnow: debug
```

Debug logs show the poll window, row counts (bounding box vs station), and the
latest timestamp per parameter. Diagnostics downloads (integration page → ⋮)
include per-station data, update health, and the last error, with the API key
redacted.
