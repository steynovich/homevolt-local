# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Home Assistant custom integration (`homevolt_local`) for local polling/control of Tibber Homevolt
battery systems. Python 3.14, aiohttp, HA Core 2026.8.0+, targets the Platinum tier of the HA
Integration Quality Scale (`py.typed`, `mypy --strict`, injected websession, `entry.runtime_data`).

## Commands

```bash
# Setup
uv venv && uv pip install pytest pytest-asyncio pytest-homeassistant-custom-component mypy ruff

source .venv/bin/activate
pytest tests/ -v                                        # full suite
pytest tests/test_sensor.py -v                          # one module
pytest tests/test_sensor.py::TestUnitConversions -v     # one class
pytest tests/test_sensor.py -k battery_soc -v           # by name
pytest tests/ --cov=custom_components.homevolt_local --cov-report=term-missing  # needs pytest-cov

# Lint / typecheck — CI runs exactly these three against custom_components/homevolt_local/
ruff check custom_components/homevolt_local/
ruff format --check custom_components/homevolt_local/    # use `ruff format .` to fix
mypy custom_components/homevolt_local/

# Live HA instance at http://localhost:8123 (mounts the component read-write into /config)
docker compose up -d && docker compose logs -f homeassistant
```

`asyncio_mode = "auto"` is set, so async tests need no `@pytest.mark.asyncio`. CI (`.github/workflows/`)
also runs hassfest and the HACS action; `release.yml` zips `custom_components/homevolt_local/` on
published releases.

## Architecture

Read path, once per 10s (`SCAN_INTERVAL`):

```
HomevoltCoordinator._async_update_data()
  └─ api.get_all_data()  →  GET /status.json /ems.json /mains_data.json /params.json
                                /schedule.json /ota_manifest.json
                            each via _request_cached() → _request() (retry + backoff + jitter)
  └─ coordinator.data = {"status": …, "ems": …, "mains": …, "params": …, "schedule": …,
                         "ota_manifest": …}
```

Key invariants in this path:

- `get_all_data()` swallows per-endpoint failures (that key becomes `{}`, entities go unavailable)
  but **deliberately re-raises `HomevoltAuthError` / `HomevoltRateLimitError`** so the coordinator can
  turn them into `ConfigEntryAuthFailed` and trigger the reauth flow. Don't broaden that `except`.
- `_request_cached()` falls back to a ≤10-minute cached response on API errors, but never for auth or
  rate-limit errors.
- 401 → `HomevoltAuthError`, 429 → `HomevoltRateLimitError` (neither is retried), 5xx/timeout → retried
  3× with exponential backoff, then `HomevoltConnectionError`.

Write path — the device has no REST write API for control, so commands go through two POST endpoints:

- `set_param(key, value)` → `POST /params.json` with `k`/`v`/`store=1`. Backs every switch, number and
  select entity.
- `send_console_command(cmd)` → `POST /console.json` with `cmd=…`. Backs buttons and services
  (`sched_set N …`, `sched_clear`, `reset_hard`). The device may answer with non-JSON console text;
  the parser detects `"returned non-zero error code"` and raises `HomevoltCommandError`.
- Every schedule-changing command first calls `_ensure_local_mode()`, which reads `/schedule.json`
  **uncached** and raises `HomevoltNotLocalModeError` unless `local_mode` is true. Callers translate
  that into a `HomeAssistantError` with translation key `not_local_mode`. `reboot` skips this gate.

### Two devices per config entry

`device.py` builds an **ECU** device (per-unit data) and, when `coordinator.is_leader`, a **Cluster**
device linked via `via_device_id`. Leader is inferred from `len(data["ems"]["ems"]) > 1`. Entity
descriptions carry `device_type`; sensor setup adds an ECU entity for every description and a second
CLUSTER entity for `device_type == CLUSTER` descriptions on leaders. `HomevoltSensor._get_data()`
rewrites cluster data as `{"ems": [aggregated], "sensors": …}` so the same `value_fn` works for both —
with no fallback to individual units, since `ems` list order is not stable.

### Entity platform pattern

Every platform uses the same shape: a frozen `kw_only` dataclass extending HA's `*EntityDescription`,
a module-level tuple of descriptions, and one `CoordinatorEntity` class that reads through it.

- `sensor.py` — `value_fn(data)` plus optional `attributes_fn`; `data_key` selects which top-level
  coordinator key is passed in (defaults to `"ems"`).
- `switch.py` / `number.py` / `select.py` / `binary_sensor.py` — `param_key`, read from
  `data["params"]` and written with `set_param`.
- `button.py` — one hand-written class per command (no description tuple).
- Every platform sets `PARALLEL_UPDATES = 1`. Unique IDs are `f"{coordinator.device_id}_{key}"`
  (or `cluster_id`).
- Entities are created unconditionally and report unavailable when data is missing — except external
  grid/solar/load sensors, which are only added if `_has_external_sensor()` finds that `type` in
  `ems.sensors` at setup time.
- `TOTAL_INCREASING` sensors return `None` instead of any value below `_last_valid_value`. This
  prevents HA statistics corruption when an offline cluster member makes aggregated energy totals dip.
  Preserve this guard when touching `native_value`.

### Services

`__init__.py` registers 12 services (`clear_schedule`, `set_idle`, `set_charge`, `set_discharge`,
`set_grid_charge`, `set_grid_discharge`, `set_grid_charge_discharge`, `set_solar_charge`,
`set_solar_charge_discharge`, `set_full_solar_export`, `set_schedule`, `reboot`), each guarded by
`hass.services.has_service()` so re-setup is idempotent. Handlers take a `device_id`, resolve it via
the device registry to a config entry, use `config_entry.runtime_data` as the coordinator, then
`async_request_refresh()`. Adding a service means touching four places: the `SERVICE_*` name and
`vol.Schema`, the handler + registration, an `api.py` method, and `services.yaml` + `strings.json`
(+ translations).

Note `set_solar_charge_discharge` and `set_schedule` are service-only; the other ten commands also
have button entities.

## API data quirks

These are the details that cost time when unknown:

- **Dual response format.** Sensors read both the real device's nested format and the OpenAPI spec's
  flat format, via `_first_not_none(...)`: e.g. SOC from `ems[0].ems_data.soc_avg` *or* `battery_soc`;
  frequency from `ems[0].ems_data.frequency` (milli-Hz) *or* `grid_frequency` (Hz).
- **`/params.json` wraps values in arrays.** `"value": [true]`, `"value": [123]`, `"value": "string"`.
  Each platform has its own `_get_param_*` helper that unwraps single-element lists.
- **Unit conversions** (helpers `_deci_to_unit`, `_centi_to_unit`, `_milli_to_unit` in `sensor.py`):
  `tmax`/`tmin`/`sys_temp` deci-°C → °C; nested `frequency` milli-Hz → Hz; `soc_avg` centi-% → %;
  inverter energy Wh → kWh; `up_time` ms → days.
- **Device identity** comes from `ems[0].ecu_id`, falling back to a regex over the hostname
  (`homevolt[_-]?…`), then the literal `"homevolt"`. Friendly name comes from the
  `ecu_mdns_instance_name` param. The config-flow unique ID is this device ID, and reconfigure aborts
  with `different_device` if it changes.
- **Zeroconf** matches `_http._tcp.local.` with name `homevolt*`; rediscovery updates `CONF_HOST`.
- Auth is optional (`BasicAuth` only when a password is set; default username `admin`). Repeated failed
  auth makes the device return 429.
- `const.py` lists more endpoints than the coordinator polls (`/nodes.json`, `/ct.json`,
  `/node_metrics.json`, `/error_report.json`) — available on the API client but unused by entities.

## Conventions

- **Translations are enforced by tests.** `tests/test_translations.py` asserts that `en.json` matches
  `strings.json` key-for-key and that `de/fi/fr/nb/nl/sv` share that structure. Any new entity,
  service, or error message means updating `strings.json` **and all 7 files** in `translations/`, or
  the suite fails. State-based icons go in `icons.json`.
- Raise user-facing errors as `HomeAssistantError`/`ConfigEntry*` with `translation_domain=DOMAIN` and
  a `translation_key`, never bare strings.
- Release bump touches both `manifest.json` and `pyproject.toml` (`version`), which are kept in sync.
- `tests/` mirrors the module layout one-to-one; shared device payload fixtures live in
  `tests/conftest.py` (`mock_ems_data`, `mock_ems_data_leader`, `mock_all_data`, …) — extend those
  rather than inlining new payloads.
- User-facing docs (entity tables, service parameters, example automations, Day-Ahead Optimizer
  integration) live in `README.md`; keep them there rather than duplicating here.

## Resources

- [Homevolt Local API docs](https://github.com/tibber/homevolt-local-api-doc) ·
  [OpenAPI spec](https://github.com/tibber/homevolt-local-api-doc/blob/main/API_DOCUMENTATION.yaml)
- [HA developer docs](https://developers.home-assistant.io/) ·
  [Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
