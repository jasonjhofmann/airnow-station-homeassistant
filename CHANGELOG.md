# Changelog

## Unreleased

Tooling/CI only — no functional changes, no release.

- ruff `target-version` lowered from `py314` to `py313`, the declared
  support floor (HA 2025.6 → Python 3.13). Pinning to the newest
  interpreter was a time-bomb: under `py314`, `ruff format` rewrites
  `except (A, B):` into the unparenthesized PEP 758 form — 3.14-only
  syntax that ships a `SyntaxError` to every HA on Python ≤ 3.13 (the
  regression that shipped in visiblair 0.6.2). mypy is unaffected (no
  pinned `python_version`; it checks against the installed HA source).
- CI: lint (ruff check, `ruff format --check`, mypy) split into its own
  3.14 job; pytest now runs a Python 3.13 + 3.14 matrix so the floor
  interpreter is exercised on every push — 3.14-only syntax can no
  longer slip through.
- One-time `ruff format` normalization pass (whitespace/line-joining
  only) now that formatting is CI-enforced.

## 0.3.4 — 2026-06-10

- Brand images are now the official AirNow brand package (the same
  assets the core `airnow` integration uses on brands.home-assistant.io),
  replacing the placeholder map-pin wordmark. The placeholder's
  `dark_logo` variants are removed: the AirNow package ships no dark
  set, and needs none — white-on-blue renders identically on dark UI,
  so Home Assistant's fallback to the standard images applies.

## 0.3.3 — 2026-06-10

- Diagnostics redact set pre-lists the raw AirNow query-parameter casing
  (`API_KEY`) so request context attached by a future revision would
  scrub automatically; the deliberate non-redaction of public station
  metadata (coordinates, AQS codes) is now documented and tested.

## 0.3.2 — 2026-06-09

Observability & maintainability pass (no functional changes).

- **Debug logging** throughout: poll window + row counts + latest
  timestamp per parameter (coordinator), station discovery results
  (config flow), per-account setup summary, and the raw query (API
  client; the key never appears in logs). Enable via the integration
  page or `logger:`.
- **Diagnostics** now include update interval, update health, and the
  last error per station.
- **Field-level help text** (`data_description`) on every config-flow
  input, including rate-limit guidance on the API key fields.
- **CONTRIBUTING.md**: architecture tour, invariants, dev setup,
  quality gates, release process.
- README: entity-attributes table, debug-logging instructions.
- **ruff** linting added and CI-enforced (alongside coverage + mypy).

## 0.3.1 — 2026-06-09

Platinum quality-scale closure (no functional changes).

- `mypy --strict` clean across the integration; enforced in CI.
- Tightened API types (explicit generics, no `Any` leaks from rows into
  entity state).
- `manifest.json` declares `quality_scale: platinum` (self-assessed;
  custom integrations are not officially scored).

## 0.3.0 — 2026-06-09

Gold quality-scale closure.

- **Diagnostics**: download per-station data dumps from the integration
  page (API key redacted).
- **Reconfigure flow**: change the API key proactively (Settings →
  Devices & Services → AirNow Station → Reconfigure).
- **Translatable errors**: coordinator failures now raise
  translation-keyed exceptions.
- README: Supported stations, Examples, Known limitations,
  Troubleshooting sections.
- 34 tests, 100% coverage maintained.
- `quality_scale.yaml`: Bronze + Silver + Gold all done/exempt.

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
