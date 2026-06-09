# Changelog

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
