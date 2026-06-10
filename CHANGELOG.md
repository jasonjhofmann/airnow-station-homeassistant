# Changelog

## 0.2.2 — 2026-06-09

Silver quality-scale closure (no functional changes).

- Test coverage 91% → 100% (32 tests): real `/aq/data/` client unit
  tests, coordinator failure modes (auth / transient / no-station-rows),
  unload, foreign-subentry skip, config-flow exception branches,
  sensor edge cases (unknown parameter, disappearing parameter,
  sentinel-only AQI).
- CI now enforces `--cov-fail-under=95`.
- README: Parameters table + Options section.
- `quality_scale.yaml`: all Silver rules done/exempt.

## 0.2.1 — 2026-06-09

Bronze quality-scale closure (no functional changes).

- In-tree brand assets (icon/logo + dark variants, original artwork;
  `scripts/generate_brand.py` regenerates them).
- Base entity moved to `entity.py` (common-modules pattern).
- Reauth flow tests (bad key, recovery, empty-response-still-valid).
- README: Removal section.
- `quality_scale.yaml`: Bronze rules all done/exempt.

## 0.2.0 — 2026-06-09

**Breaking (pre-release, no migration):** restructured to one account-level
config entry (API key) with **station subentries**.

- Account flow asks only for the API key; reauth lives on the account entry.
- Stations are added via "Add monitoring station" subentry flows
  (coordinates → discovery pick-list); subentry unique ID = full AQS code,
  so duplicate stations are rejected per account.
- One shared API client; one coordinator per station subentry; entities and
  devices are bound to their subentry (removing a station cleans them up).
- Entry reloads automatically when subentries change.

## 0.1.0 — 2026-06-09

Initial scaffold.

- `/aq/data/` (query data) client in pyairnow house style (`api.py`),
  standalone-importable and intended for an eventual upstream PR.
- Two-step config flow: API key + coordinates → pick from discovered
  stations (last 3 h of data within ~25 km), unique ID = full AQS code.
- Reauth flow on rejected API key.
- 15-minute polling coordinator with a ±0.002° bounding box around the
  station, AQS-code filtering, and -999 sentinel handling.
- Sensors per reported parameter (concentration + AQI) plus overall AQI
  with dominant pollutant/category attributes.
- Config-flow and sensor test suites; hassfest/HACS/pytest CI.
