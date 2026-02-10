# ha-homevolt-local

Home Assistant custom integration for local control of Tibber Homevolt battery systems.

## Tech Stack

- Python 3.12+
- Home Assistant Core 2024.1.0+
- aiohttp for async HTTP requests
- Meets Gold tier of HA Integration Quality Scale

## Project Structure

```
ha-homevolt-local/
├── custom_components/
│   └── homevolt_local/
│       ├── __init__.py          # Integration setup, runtime_data
│       ├── api.py               # API client (retry, caching)
│       ├── config_flow.py       # UI configuration flow
│       ├── const.py             # Constants and endpoints
│       ├── coordinator.py       # DataUpdateCoordinator
│       ├── diagnostics.py       # Debug data export with redaction
│       ├── binary_sensor.py     # Binary sensor entities (MQTT valid)
│       ├── button.py            # Button entities
│       ├── number.py            # Number entities (fuse sizes, LED settings)
│       ├── select.py            # Select entities (LED strip mode)
│       ├── sensor.py            # Sensor entity definitions
│       ├── services.yaml        # Service definitions
│       ├── switch.py            # Switch entities (settings, OTA)
│       ├── manifest.json        # Integration manifest
│       ├── strings.json         # UI strings
│       ├── icons.json           # State-based icons
│       └── translations/
│           ├── de.json          # German translations
│           ├── en.json          # English translations
│           ├── fi.json          # Finnish translations
│           ├── fr.json          # French translations
│           ├── nb.json          # Norwegian translations
│           ├── nl.json          # Dutch translations
│           └── sv.json          # Swedish translations
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures
│   ├── test_config_flow.py      # Config flow tests
│   ├── test_diagnostics.py      # Diagnostics tests
│   ├── test_init.py             # Integration setup tests
│   ├── test_sensor.py           # Sensor entity tests
│   ├── test_binary_sensor.py    # Binary sensor tests
│   ├── test_button.py           # Button entity tests
│   ├── test_number.py           # Number entity tests
│   ├── test_select.py           # Select entity tests
│   └── test_switch.py           # Switch entity tests
├── config/
│   └── configuration.yaml       # HA dev config
├── docker-compose.yaml          # Local HA test instance
├── hacs.json                    # HACS configuration
├── pyproject.toml               # Project/test config
├── README.md                    # User documentation
└── CLAUDE.md                    # This file
```

## API Client Features

- **Exponential backoff retry**: 3 retries with 1s/2s/4s delays
- **Response caching**: 10-minute cache fallback on failures
- **Optional authentication**: Supports both authenticated and open devices
- **Endpoints used**: `/status.json`, `/ems.json`, `/mains_data.json`, `/params.json`, `/schedule.json`
- **Dual format support**: Supports both nested (actual API) and flat (OpenAPI spec) response formats

## Entity Platforms

### Sensors
- **Battery SOC**: State of charge (centi-% → %, 1 decimal precision)
- **Inverter Power/Energy**: Power and energy metrics
- **EMS Frequency**: Grid frequency
- **Operation State**: Current EMS state
- **Battery State**: Current battery state (charging, discharging, etc.)
- **Schedule Mode**: Local/Remote with schedule attributes
- **EMS Mode**: Leader/Follower based on number of units in cluster
- **Firmware Version**: ECU firmware version (diagnostic)
- **Alarm/Warning/Info Messages**: Count of active alarms/warnings/info messages with messages attribute (diagnostic)
- **Uptime**: Device uptime in days (diagnostic, disabled by default)
- **Mains Voltage/Frequency**: Grid measurements (diagnostic, disabled by default)
- **System Temperature**: ECU temperature
- **EMS Prediction Sensors**: Available charge/discharge power and energy metrics
  - Available Charge Power (`avail_ch_pwr`)
  - Available Discharge Power (`avail_di_pwr`)
  - Available Charge Energy (`avail_ch_energy`)
  - Available Discharge Energy (`avail_di_energy`)
  - Available Inverter Charge Power (`avail_inv_ch_pwr`)
  - Available Inverter Discharge Power (`avail_inv_di_pwr`)
- **External Sensors** (ECU-only, auto-detected from sensors array):
  - **Grid**: Power, Energy Imported/Exported, Signal Strength (enabled by default)
  - **Solar**: Power, Energy Imported/Exported (Energy Exported disabled), Signal Strength (enabled by default)
  - **Load**: Power, Energy Imported/Exported, Signal Strength (disabled by default)

### Binary Sensors (Diagnostic)
- **MQTT Valid**: MQTT connection status
- **WiFi Valid**: WiFi connection status
- **LTE Valid**: LTE/cellular connection status

### Switches
- **Settings Local**: Enable/disable local settings mode
- **OTA Updates Enabled**: Master OTA enable switch (diagnostic)
- **OTA Update ESP32/Hub Web/BG95-M3**: Component-specific OTA switches (diagnostic)

### Numbers (Configuration)
- **Main/Group Fuse Size**: Fuse amperage settings (1-100A)
- **LED Strip Brightness** (max/min): 0-100%
- **LED Strip Hue**: 0-360°
- **LED Strip Saturation**: 0-100%

### Buttons
- **Clear Schedule**: Clear all scheduled entries (config)
- **Set Idle**: Set battery to idle mode (config)
- **Set Charge**: Set battery to charge mode (config)
- **Set Discharge**: Set battery to discharge mode (config)
- **Set Solar Charge**: Charge from solar only (config)
- **Set Full Solar Export**: Export all solar production (config)
- **Reboot**: Hardware reset of the device (diagnostic, restart device class) — does not require local mode

### Selects (Configuration)
- **LED Strip Mode**: off, on, soc, dem, ser (shows "Unset" when empty)

## Entity Behavior

- **All entities created unconditionally**: Show "unavailable" when data is missing
- **Automatic availability**: Become available when data appears (no reload needed)
- **Entity categories**: CONFIG for settings, DIAGNOSTIC for system info
- **External sensor detection**: Grid/Solar/Load sensors only created on ECU devices when detected in API data

## Response Format Compatibility

Sensors support both the actual API nested format and OpenAPI flat format:

| Sensor | Nested Format (Actual API) | Flat Format (OpenAPI) |
|--------|---------------------------|----------------------|
| Battery SOC | `ems[0].ems_data.soc_avg` | `battery_soc` |
| Inverter Power | `ems[0].ems_data.power` | `inverter_power` |
| EMS Frequency | `ems[0].ems_data.frequency` (milli-Hz) | `grid_frequency` (Hz) |
| Operation State | `ems[0].op_state_str` | `ems_state` |
| Mains Voltage | `mains_voltage_rms` | - |
| Uptime | `up_time` (ms → days) | - |
| Schedule | `local_mode` → "local"/"remote" | - |
| Alarm/Warning/Info | `ems_data.*_str` (list length) | - |
| EMS Prediction | `ems[0].ems_prediction.*` | - |

## Unit Conversions

| Field | API Unit | Display Unit | Conversion |
|-------|----------|--------------|------------|
| Temperature (tmax, tmin, sys_temp) | deci-°C | °C | ÷10 |
| EMS Frequency (nested) | milli-Hz | Hz | ÷1000 |
| Battery SOC (soc_avg) | centi-% | % | ÷100 |
| Inverter Energy | Wh | kWh | ÷1000 |
| Uptime (up_time) | ms | days | ÷86400000 |

## Params Format

The `/params.json` endpoint returns parameters with values wrapped in arrays:

| Field | Format |
|-------|--------|
| Boolean params | `"value": [true]` or `"value": [false]` |
| String params | `"value": "string"` |
| Integer params | `"value": [123]` |

## Config Flow Features

- **User setup**: Manual configuration via hostname/IP and optional credentials
- **Zeroconf discovery**: Automatic detection of devices broadcasting `_http._tcp.local.` with `homevolt` hostname
- **Reauthentication flow**: Prompts user when credentials become invalid (401 errors)
- **Reconfiguration flow**: Change host/credentials without deleting the integration
- **Discovery update**: Host automatically updates when device is rediscovered at new address

## Development

### Running Tests

```bash
# Create virtual environment and install dependencies
uv venv
uv pip install pytest pytest-asyncio pytest-homeassistant-custom-component

# Run tests with coverage (90%+ coverage)
source .venv/bin/activate && pytest tests/ -v --cov=custom_components.homevolt_local --cov-report=term-missing
```

### Local HA Instance

```bash
# Start Home Assistant
docker compose up -d

# View logs
docker compose logs -f homeassistant

# Access at http://localhost:8123
```

### Code Style

```bash
# Format and lint
ruff check --fix .
ruff format .
```

## Quality Scale Compliance (Platinum)

### Bronze ✅
- ✅ config-flow: UI setup with data_description
- ✅ entity-unique-id: All entities have unique IDs
- ✅ has-entity-name: Uses `_attr_has_entity_name = True`
- ✅ runtime-data: Uses `entry.runtime_data`
- ✅ test-before-configure: Tests connection in config flow
- ✅ test-before-setup: Tests connection during setup
- ✅ unique-config-entry: Prevents duplicates via unique_id
- ✅ appropriate-polling: 10 second interval
- ✅ config-flow-test-coverage: Full test coverage

### Silver ✅
- ✅ integration-owner: @steynovich
- ✅ parallel-updates: `PARALLEL_UPDATES = 1`
- ✅ reauthentication-flow: `async_step_reauth` for credential updates
- ✅ test-coverage: 90%+ (498 tests)
- ✅ config-entry-unloading: Clean unload with coordinator cancellation
- ✅ entity-unavailable: Sensors unavailable when data missing
- ✅ log-when-unavailable: Debug logging on update failures

### Gold ✅
- ✅ diagnostics: `diagnostics.py` with sensitive data redaction
- ✅ discovery: Zeroconf mDNS (`_http._tcp.local.` with `homevolt` hostname)
- ✅ discovery-update-info: Host updates on rediscovery
- ✅ reconfiguration-flow: `async_step_reconfigure` for host/credential changes
- ✅ entity-disabled-by-default: Diagnostic sensors (Uptime, System Temperature, Mains Voltage, Mains Frequency)
- ✅ entity-category: Diagnostic category for system sensors
- ✅ entity-device-class: Appropriate device classes (power, energy, temperature, etc.)
- ✅ entity-translations: Translated sensor names in `strings.json`
- ✅ exception-translations: Translated error messages
- ✅ icon-translations: `icons.json` with state-based icons

### Platinum ✅
- ✅ async-dependency: Uses `aiohttp` (fully async HTTP library)
- ✅ inject-websession: API accepts session, uses `async_get_clientsession(hass)`
- ✅ strict-typing: PEP 561 compliant with `py.typed` marker, passes `mypy --strict`

## Resources

- [Homevolt Local API Documentation](https://github.com/tibber/homevolt-local-api-doc)
- [OpenAPI/Swagger Specification](https://github.com/tibber/homevolt-local-api-doc/blob/main/API_DOCUMENTATION.yaml)
- [Postman Collection](https://github.com/tibber/homevolt-local-api-doc/blob/main/Tibber_ECU_API.postman_collection.json)
- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
- [HACS Publishing Guide](https://www.hacs.xyz/docs/publish/)
