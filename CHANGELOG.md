# Changelog

## 0.3.8 — 2026-06-11

- **HACS validation now runs without `ignore: brands`.** The escape
  hatch was vestigial — brand assets have shipped in-package at
  `custom_components/airnow_station/brand/` since 0.3.4 and satisfy
  the check directly. Removing it is a prerequisite for the
  hacs/default registry submission, whose checklist requires a green
  HACS action without the `ignore` key. No functional changes.

## 0.3.7 — 2026-06-10

- **Null/missing `RawConcentration` no longer leaks a `None` attribute.**
  A row with a valid `Value` but a JSON `null` (or absent)
  `RawConcentration` exposed `raw_concentration: None` on the
  concentration sensor, while the API's -999 sentinel already omitted
  the attribute. Null and missing are now treated exactly like the
  sentinel at the attribute layer: the attribute is omitted. Cosmetic
  hardening only — no crash involved, valid raw concentrations
  unaffected.

## 0.3.6 — 2026-06-10

Adjacent-issue sweep: registry-collision prevention, reload dedup, and
parsing hardening.

- **Duplicate stations across account entries are now rejected.** A
  station's subentry unique ID is only unique within its parent account
  entry, but entity and device unique IDs derive from the AQS code
  alone — so adding the same station under a second account entry
  (a second API key) collided in the entity/device registries. The
  station-picker step now checks every account entry of the domain and
  aborts with `already_configured` (message updated to say the station
  may live on another account entry). The unique-ID format is
  deliberately unchanged: rewriting it would orphan every existing
  entity.
- **Key changes via reauth/reconfigure no longer reload the entry
  twice.** `async_update_reload_and_abort` scheduled a reload while the
  entry's update listener (needed so subentry add/remove triggers a
  reload) fired on the same data update and scheduled a second — two
  full setups, 2 × N station API calls per key change. HA 2026.6 also
  deprecates that flow-helper/listener combination outright (logged,
  breaks in 2026.12). The flows now just update the entry data and let
  the update listener own the reload; they schedule it directly only
  when the listener cannot fire — the entry is not loaded (reauth after
  a failed setup) or the key is unchanged. Exactly one reload in every
  path, verified by setup-counting tests for reauth (loaded and failed
  entries) and subentry add/remove.
- **Row-parsing hardening.** A JSON `null` `Value` slipped past the
  -999 sentinel filter and crashed `float(row["Value"])` in the
  concentration sensor; a row omitting the `AQI` key was a hard
  `KeyError` in the AQI sensors. `latest_by_parameter()` now skips rows
  with missing/null `Value` (falling back to the prior hour exactly
  like the sentinel) and normalizes a missing or null `AQI` to the
  sentinel, so AQI sensors report unknown while the concentration still
  reports.
- `scripts/smoke_test.py`: the `lat` argument guard was off by one
  (`len(sys.argv) > 2`), so passing only a latitude silently used the
  default coordinates. Dev script only.

## 0.3.5 — 2026-06-10

Resilience release: one station's outage no longer takes down the whole
account entry, and stalled API requests time out instead of hanging.

- **Per-station failure isolation.** Setup previously ran
  `async_config_entry_first_refresh` per station, so a single station in
  a routine AirNow data outage raised `ConfigEntryNotReady` for the
  entire account entry — blocking restarts, adding stations, and key
  rotation for all healthy stations. Each station coordinator now
  refreshes independently (`async_refresh`): a failed station loads
  degraded and keeps retrying on its 15-minute schedule while every
  other station works normally. A station with no data at startup gets
  no sensors yet (they derive from the parameters it reports); the entry
  reloads automatically on its first successful poll to create them.
  Only an account-wide auth failure — every station rejecting the key —
  still fails setup, so reauthentication fires as before.
- **10-second request timeout.** pyairnow's `ClientTimeout` only applies
  to sessions it creates itself; with Home Assistant's injected shared
  session, requests ran under aiohttp's 300 s default. `bbox()` now
  enforces `asyncio.timeout(10)` (matching pyairnow's intended default),
  and timeouts map to the existing error taxonomy: `UpdateFailed` in the
  coordinator, `cannot_connect` in the flows.
- **Reauth/reconfigure flows no longer crash on unexpected errors.**
  Both steps only caught `InvalidKeyError` and connector-type errors; a
  timeout, `ServerDisconnectedError`, or other surprise aborted the flow
  with Home Assistant's generic "unknown error" page. They now redisplay
  the form with `cannot_connect`/`unknown` (logged), matching the user
  step's handling.
- README: the Options section claimed reconfigure was "planned but not
  yet implemented" — it shipped in 0.3.0; the section now documents the
  actual Reconfigure path and the new degraded-station behavior is noted
  under Troubleshooting.

Plus the previously unreleased tooling/CI changes:

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
