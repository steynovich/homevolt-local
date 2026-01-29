# Homevolt Local Integration for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Test](https://github.com/steynovich/homevolt-local/actions/workflows/test.yml/badge.svg)](https://github.com/steynovich/homevolt-local/actions/workflows/test.yml)
[![Validate](https://github.com/steynovich/homevolt-local/actions/workflows/validate.yml/badge.svg)](https://github.com/steynovich/homevolt-local/actions/workflows/validate.yml)

Local API integration for Tibber Homevolt battery systems.

## Overview

This integration allows you to monitor and control your Homevolt battery system locally without cloud dependencies. It connects directly to your Homevolt device over your local network.

**Quality Scale:** Platinum tier compliance (strict typing, async dependency injection, full test coverage)

## Supported Devices

- Tibber Homevolt Battery Systems (all models with local API enabled)

## Supported Languages

- English (en)
- German (de)
- Dutch (nl)
- Norwegian (nb)
- Swedish (sv)

## Features

- **Battery monitoring**: State of charge, power, energy, temperature
- **EMS prediction sensors**: Available charge/discharge power and energy
- **Connectivity status**: MQTT, WiFi, LTE connection monitoring
- **Battery control services**: Charging, discharging, and grid modes
- **Quick action buttons**: Common battery operations
- **LED strip configuration**: Mode, brightness, hue, saturation
- **Fuse configuration**: Main and group fuse size settings
- **OTA update control**: Enable/disable firmware updates
- **Automatic device discovery**: Via Zeroconf/mDNS
- **Reauthentication flow**: When credentials change
- **Reconfiguration**: Without removing the device
- **Diagnostics export**: For debugging and support

## Prerequisites

- Home Assistant 2024.1.0 or newer
- Homevolt device accessible on your local network
- Local API enabled on your Homevolt (contact Tibber support if needed)

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL and select "Integration" as the category
6. Click "Add"
7. Search for "Homevolt Local" and install it
8. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/homevolt_local` folder to your Home Assistant `config/custom_components` directory
2. Restart Home Assistant

## Configuration

### Automatic Discovery

If your Homevolt device broadcasts mDNS (hostname starting with `homevolt`), Home Assistant will automatically detect it. You'll see a notification to configure the discovered device.

> **Note:** Discovery requires mDNS to work on your network. If running Home Assistant in Docker on macOS, you may need host networking mode for discovery to work.

### Manual Setup

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Homevolt Local"
4. Enter your Homevolt device's hostname or IP address
   - Example: `homevolt-abc123.local` or `192.168.1.100`
5. If authentication is enabled on your device, enter username and password
6. Click **Submit**

## Entities

### Sensors

| Sensor | Description | Unit |
|--------|-------------|------|
| Battery State of Charge | Current battery level | % |
| Battery State | Current battery state (charging, discharging, etc.) | - |
| Inverter Power | Inverter output | W |
| Inverter Energy Produced | Total energy produced | kWh |
| Inverter Energy Consumed | Total energy consumed | kWh |
| EMS Frequency | EMS measured frequency | Hz |
| System Temperature | Inverter/EMS temperature | °C |
| Available Capacity | Usable battery capacity | Wh |
| Operation State | Current operating mode | - |
| Schedule Mode | Schedule control mode (local/remote) | - |
| EMS Mode | Cluster mode (Leader/Follower) | - |
| Firmware Version | ECU firmware version | - |
| Alarm/Warning/Info Messages | Count of active messages | - |
| Available Charge Power | Available power for charging | W |
| Available Discharge Power | Available power for discharging | W |
| Available Charge Energy | Available energy for charging | Wh |
| Available Discharge Energy | Available energy for discharging | Wh |
| Available Inverter Charge Power | Available inverter charge power | W |
| Available Inverter Discharge Power | Available inverter discharge power | W |

**External sensors (ECU-only, auto-detected):**

| Sensor | Description | Unit |
|--------|-------------|------|
| Grid Power | Grid sensor power measurement | W |
| Grid Energy Imported | Energy imported from grid | kWh |
| Grid Energy Exported | Energy exported to grid | kWh |
| Grid Signal Strength | Grid sensor RSSI | dBm |
| Solar Power | Solar sensor power measurement | W |
| Solar Energy Imported | Energy produced by solar | kWh |
| Load Power | Load sensor power measurement | W |
| Load Energy Imported | Energy consumed by loads | kWh |
| Load Energy Exported | Energy from loads | kWh |

> **Note:** External sensors only appear when the respective sensor (grid/solar/load) is detected on your device. Grid and Solar signal strength sensors are enabled by default.

**Diagnostic sensors (disabled by default):**

| Sensor | Description | Unit |
|--------|-------------|------|
| Mains Voltage | Grid voltage (RMS) | V |
| Mains Frequency | Grid frequency | Hz |
| Uptime | System uptime | days |
| Solar Energy Exported | Energy exported from solar (rarely used) | kWh |
| Load Signal Strength | Load sensor RSSI | dBm |

### Binary Sensors

| Sensor | Description | Category |
|--------|-------------|----------|
| MQTT Valid | MQTT connection status | Diagnostic |
| WiFi Valid | WiFi connection status | Diagnostic |
| LTE Valid | LTE/cellular connection status | Diagnostic |

### Switches

| Switch | Description | Category |
|--------|-------------|----------|
| Settings Local | Enable/disable local settings mode | - |
| OTA Updates Enabled | Master OTA enable switch | Diagnostic |
| OTA Update ESP32 | ESP32 OTA updates | Diagnostic |
| OTA Update Hub Web | Hub Web OTA updates | Diagnostic |
| OTA Update BG95-M3 | BG95-M3 OTA updates | Diagnostic |

### Numbers (Configuration)

| Entity | Description | Range |
|--------|-------------|-------|
| Main Fuse Size | Main fuse amperage | 1-100 A |
| Group Fuse Size | Group fuse amperage | 1-100 A |
| LED Strip Brightness Max | Maximum LED brightness | 0-100% |
| LED Strip Brightness Min | Minimum LED brightness | 0-100% |
| LED Strip Hue | LED color hue | 0-360° |
| LED Strip Saturation | LED color saturation | 0-100% |

### Selects (Configuration)

| Entity | Description | Options |
|--------|-------------|---------|
| LED Strip Mode | LED strip display mode | off, on, soc, dem, ser |

### Buttons

| Button | Description |
|--------|-------------|
| Clear Schedule | Clear all scheduled entries |
| Set Idle | Set battery to idle mode |
| Set Charge | Set battery to charge mode |
| Set Discharge | Set battery to discharge mode |
| Set Solar Charge | Charge from solar only |
| Set Full Solar Export | Export all solar production |

## Sensor Data Sources

Each sensor maps to a specific API endpoint and JSON key path:

| Sensor | Endpoint | JSON Key Path | Conversion |
|--------|----------|---------------|------------|
| Battery State of Charge | `/ems.json` | `ems[0].ems_data.soc_avg` | centi-% → % (÷100) |
| Inverter Power | `/ems.json` | `ems[0].ems_data.power` | - |
| Inverter Energy Produced | `/ems.json` | `ems[0].ems_data.energy_produced` | Wh → kWh (÷1000) |
| Inverter Energy Consumed | `/ems.json` | `ems[0].ems_data.energy_consumed` | Wh → kWh (÷1000) |
| EMS Frequency | `/ems.json` | `ems[0].ems_data.frequency` | milli-Hz → Hz (÷1000) |
| System Temperature | `/ems.json` | `ems[0].ems_data.sys_temp` | deci-°C → °C (÷10) |
| Available Capacity | `/ems.json` | `ems[0].ems_data.avail_cap` | - |
| Operation State | `/ems.json` | `ems[0].op_state_str` | - |
| Mains Voltage | `/mains_data.json` | `mains_voltage_rms` | - |
| Mains Frequency | `/mains_data.json` | `frequency` | - |
| Uptime | `/status.json` | `up_time` | ms → days (÷86400000) |
| Schedule | `/schedule.json` | `local_mode` | true → "local", false → "remote" |
| Available Charge Power | `/ems.json` | `ems[0].ems_prediction.avail_ch_pwr` | - |
| Available Discharge Power | `/ems.json` | `ems[0].ems_prediction.avail_di_pwr` | - |
| Available Charge Energy | `/ems.json` | `ems[0].ems_prediction.avail_ch_energy` | - |
| Available Discharge Energy | `/ems.json` | `ems[0].ems_prediction.avail_di_energy` | - |
| Available Inverter Charge Power | `/ems.json` | `ems[0].ems_prediction.avail_inv_ch_pwr` | - |
| Available Inverter Discharge Power | `/ems.json` | `ems[0].ems_prediction.avail_inv_di_pwr` | - |

The Schedule Mode sensor also exposes extra state attributes:
- `schedule_id`: Unique identifier for the current schedule
- `schedule`: Array of schedule entries, each enhanced with:
  - `type_name`: Human-readable control mode (e.g., "inverter_charge", "grid_discharge")
  - `from_utc`: ISO 8601 UTC timestamp for schedule start
  - `to_utc`: ISO 8601 UTC timestamp for schedule end

### Schedule Control Modes

| Type | Name | Description |
|------|------|-------------|
| 0 | idle | Battery standby (no charge/discharge) |
| 1 | inverter_charge | Charge battery via inverter from grid/solar |
| 2 | inverter_discharge | Discharge battery via inverter to home/grid |
| 3 | grid_charge | Charge from grid with power setpoint |
| 4 | grid_discharge | Discharge to grid with power setpoint |
| 5 | grid_charge_discharge | Bidirectional grid control |
| 6 | frequency_reserve | Frequency regulation service mode |
| 7 | solar_charge | Charge from solar production only |
| 8 | solar_charge_discharge | Solar-based grid management |
| 9 | full_solar_export | Export all solar production |

## Services

The integration provides services to control battery charging modes. **All services require local mode to be enabled** on the device first (via the "Settings local" switch).

### Available Services

| Service | Description |
|---------|-------------|
| `homevolt_local.clear_schedule` | Clear all scheduled charging entries |
| `homevolt_local.set_idle` | Set battery to idle mode (no charge/discharge) |
| `homevolt_local.set_charge` | Set to charge mode (inverter charge from grid/solar) |
| `homevolt_local.set_discharge` | Set to discharge mode (inverter discharge to home/grid) |
| `homevolt_local.set_grid_charge` | Force charge from grid |
| `homevolt_local.set_grid_discharge` | Force discharge to grid |
| `homevolt_local.set_grid_charge_discharge` | Bidirectional grid control |
| `homevolt_local.set_solar_charge` | Charge from solar production only |
| `homevolt_local.set_solar_charge_discharge` | Solar-based grid management |
| `homevolt_local.set_full_solar_export` | Export all solar production |
| `homevolt_local.set_schedule` | Replace battery schedule with a list of entries |

### Service Parameters

**set_idle:**
- `offline` (optional): Take inverter offline during idle mode

**set_charge / set_discharge:**
- `setpoint` (optional): Power setpoint in watts
- `min_soc` (optional): Minimum state of charge (%)
- `max_soc` (optional): Maximum state of charge (%)

**set_grid_charge / set_grid_discharge:**
- `setpoint` (optional): Power setpoint in watts
- `min_soc` (optional): Minimum state of charge (%)
- `max_soc` (optional): Maximum state of charge (%)

**set_grid_charge_discharge:**
- `setpoint` (required): Power setpoint in watts
- `charge_setpoint` (optional): Maximum charge power in watts
- `discharge_setpoint` (optional): Maximum discharge power in watts
- `min_soc` (optional): Minimum state of charge (%)
- `max_soc` (optional): Maximum state of charge (%)

**set_solar_charge / set_full_solar_export:**
- `setpoint` (optional): Power setpoint in watts
- `min_soc` (optional): Minimum state of charge (%)
- `max_soc` (optional): Maximum state of charge (%)

**set_solar_charge_discharge:**
- `setpoint` (optional): Power setpoint in watts
- `charge_setpoint` (optional): Maximum charge power in watts
- `discharge_setpoint` (optional): Maximum discharge power in watts
- `min_soc` (optional): Minimum state of charge (%)
- `max_soc` (optional): Maximum state of charge (%)

**set_schedule:**
- `schedule` (required): List of schedule entries, each containing:
  - `type` (required): Control mode (0-9, see Schedule Control Modes table above)
  - `from_time` (optional): Start time in ISO 8601 format (`YYYY-MM-DDTHH:mm:ss`)
  - `to_time` (optional): End time in ISO 8601 format (`YYYY-MM-DDTHH:mm:ss`)
  - `min_soc` (optional): Minimum state of charge (0-100%)
  - `max_soc` (optional): Maximum state of charge (0-100%)
  - `setpoint` (optional): Power setpoint in watts
  - `max_charge` (optional): Maximum charge power in watts
  - `max_discharge` (optional): Maximum discharge power in watts
  - `import_limit` (optional): Grid import limit in watts
  - `export_limit` (optional): Grid export limit in watts

> **Note:** The first entry in the schedule replaces all existing entries. Subsequent entries are added to the schedule.

### Example Service Call

```yaml
service: homevolt_local.set_charge
data:
  device_id: <your_device_id>
  setpoint: 5000
  max_soc: 90
```

## Reconfiguration

To change the host address or credentials without removing the integration:

1. Go to **Settings** → **Devices & Services**
2. Find "Homevolt Local" integration
3. Click **Configure**
4. Update the host, username, or password as needed
5. Click **Submit**

The integration will reconnect with the new settings without losing your entity history.

## Diagnostics

To help with troubleshooting, you can download diagnostic data:

1. Go to **Settings** → **Devices & Services**
2. Find "Homevolt Local" integration
3. Click on the device
4. Click the three dots menu → **Download diagnostics**

The diagnostic data includes:
- Configuration (with sensitive data redacted)
- Current coordinator data
- API endpoint responses

> **Privacy:** Host addresses, usernames, passwords, and serial numbers are automatically redacted from the diagnostic export.

## Troubleshooting

### Cannot connect to device

- Verify the device is powered on and connected to your network
- Check that you can ping the device: `ping homevolt-xxx.local`
- Try using the IP address instead of hostname
- Ensure no firewall is blocking the connection

### Authentication errors

- Verify username and password are correct
- Default username is `admin` if authentication is enabled
- Contact Tibber support if you've forgotten credentials

### Sensors showing unavailable

- The integration polls every 10 seconds
- Some sensors may not be available depending on your system configuration
- Check Home Assistant logs for specific error messages

### Reauthentication required

If you see a "Reauthentication required" notification:

1. Go to **Settings** → **Devices & Services**
2. Find "Homevolt Local" with the attention badge
3. Click **Reconfigure**
4. Enter the correct username and password
5. Click **Submit**

### Discovery not finding my device

- Ensure your Homevolt device hostname starts with `homevolt`
- Verify mDNS is working on your network: try `ping homevolt-xxx.local`
- If using Docker, ensure the container has access to the host network for mDNS
- You can always add the device manually using its IP address

## Example Automations

### Low Battery Alert

```yaml
automation:
  - alias: "Homevolt Low Battery Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.homevolt_battery_state_of_charge
        below: 20
    action:
      - service: notify.mobile_app
        data:
          title: "Battery Low"
          message: "Homevolt battery is at {{ states('sensor.homevolt_battery_state_of_charge') }}%"
```

### Charge During Cheap Hours

```yaml
automation:
  - alias: "Charge battery during cheap electricity"
    trigger:
      - platform: time
        at: "02:00:00"
    action:
      - service: homevolt_local.set_grid_charge
        data:
          device_id: <your_device_id>
          setpoint: 5000
          max_soc: 90
```

### Stop Charging at Target SOC

```yaml
automation:
  - alias: "Stop charging at 90%"
    trigger:
      - platform: numeric_state
        entity_id: sensor.homevolt_battery_state_of_charge
        above: 90
    action:
      - service: homevolt_local.set_idle
        data:
          device_id: <your_device_id>
```

### Time-of-Use Schedule

```yaml
automation:
  - alias: "Set daily battery schedule"
    trigger:
      - platform: time
        at: "00:00:00"
    action:
      - service: homevolt_local.set_schedule
        data:
          device_id: <your_device_id>
          schedule:
            - type: 3  # Grid charge during cheap hours
              from_time: "2024-01-15T02:00:00"
              to_time: "2024-01-15T06:00:00"
              max_charge: 5000
              max_soc: 90
            - type: 4  # Grid discharge during peak hours
              from_time: "2024-01-15T17:00:00"
              to_time: "2024-01-15T20:00:00"
              max_discharge: 3000
              min_soc: 20
```

## Known Limitations

- **Docker on macOS**: Zeroconf discovery may not work when running Home Assistant in Docker on macOS unless using host networking mode
- **Rate limiting**: The API has no documented rate limits, but the integration polls every 10 seconds to be conservative
- **Local mode required**: Battery control services require "Settings local" to be enabled to prevent conflicts with Tibber cloud control

## Resources

- [Homevolt Local API Documentation](https://github.com/tibber/homevolt-local-api-doc)
- [Home Assistant Community](https://community.home-assistant.io/)

## License

MIT License
