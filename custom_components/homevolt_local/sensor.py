"""Sensor platform for Homevolt Local integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HomevoltConfigEntry
from .coordinator import HomevoltCoordinator
from .device import DeviceType, get_cluster_device_info, get_ecu_device_info

# Limit parallel updates to avoid overwhelming the device
PARALLEL_UPDATES = 1

# Schedule control mode types from Battery Control Guide
# https://github.com/tibber/homevolt-local-api-doc/blob/main/BATTERY_CONTROL_GUIDE.md
SCHEDULE_CONTROL_MODES: dict[int, str] = {
    0: "idle",
    1: "inverter_charge",
    2: "inverter_discharge",
    3: "grid_charge",
    4: "grid_discharge",
    5: "grid_charge_discharge",
    6: "frequency_reserve",
    7: "solar_charge",
    8: "solar_charge_discharge",
    9: "full_solar_export",
}


# Helper functions to extract data from nested API responses


def _get_ems_data(data: dict[str, Any]) -> dict[str, Any]:
    """Get EMS data from the local device (first EMS unit)."""
    ems_data = _get_first_ems(data).get("ems_data", {})
    return ems_data if isinstance(ems_data, dict) else {}


def _get_first_ems(data: dict[str, Any]) -> dict[str, Any]:
    """Get first EMS unit data."""
    ems_list = data.get("ems", [])
    if isinstance(ems_list, list) and ems_list:
        first = ems_list[0]
        return first if isinstance(first, dict) else {}
    return {}


def _get_first_bms(data: dict[str, Any]) -> dict[str, Any]:
    """Get first BMS data from first EMS unit."""
    ems = _get_first_ems(data)
    bms_list = ems.get("bms_data", [])
    if isinstance(bms_list, list) and bms_list:
        first = bms_list[0]
        return first if isinstance(first, dict) else {}
    return {}


def _get_first_ems_info(data: dict[str, Any]) -> dict[str, Any]:
    """Get ems_info from the first EMS unit."""
    ems_info = _get_first_ems(data).get("ems_info", {})
    return ems_info if isinstance(ems_info, dict) else {}


def _get_ems_prediction(data: dict[str, Any]) -> dict[str, Any]:
    """Get ems_prediction from the first EMS unit."""
    prediction = _get_first_ems(data).get("ems_prediction", {})
    return prediction if isinstance(prediction, dict) else {}


def _get_aggregated_ems_info(data: dict[str, Any]) -> dict[str, Any]:
    """Get aggregated ems_info from cluster leader data."""
    aggregated = data.get("aggregated", {})
    if isinstance(aggregated, dict):
        ems_info = aggregated.get("ems_info", {})
        return ems_info if isinstance(ems_info, dict) else {}
    return {}


def _get_sensor_by_type(data: dict[str, Any], sensor_type: str) -> dict[str, Any]:
    """Get sensor data by type (grid, solar, load) from EMS sensors array.

    The sensors array is at the top level of the EMS response, alongside
    the ems and aggregated objects. Each sensor has a type field
    that identifies its type (grid, solar, load).
    """
    sensors = data.get("sensors", [])
    if isinstance(sensors, list):
        for sensor in sensors:
            if isinstance(sensor, dict) and sensor.get("type") == sensor_type:
                return sensor
    return {}


def _get_local_ems(data: dict[str, Any]) -> dict[str, Any]:
    """Get local EMS entry (where ecu_host is empty)."""
    ems_list = data.get("ems", [])
    if isinstance(ems_list, list):
        for ems in ems_list:
            if isinstance(ems, dict) and not ems.get("ecu_host"):
                return ems
    return {}


def _list_length_or_none(value: Any) -> int | None:
    """Return length of list or None if not a list."""
    if isinstance(value, list):
        return len(value)
    return None


def _deci_to_unit(value: float | int | None) -> float | None:
    """Convert deci-unit (e.g., deci-degrees) to unit (e.g., degrees)."""
    if value is None:
        return None
    return value / 10.0


def _centi_to_unit(value: float | int | None) -> float | None:
    """Convert centi-unit (e.g., centi-percent) to unit (e.g., percent)."""
    if value is None:
        return None
    return value / 100.0


def _milli_to_unit(value: float | int | None) -> float | None:
    """Convert milli-unit (e.g., milli-Hz) to unit (e.g., Hz)."""
    if value is None:
        return None
    return value / 1000.0


def _get_param_string(params: list[dict[str, Any]], name: str) -> str | None:
    """Extract a string parameter value from params list."""
    if not isinstance(params, list):
        return None
    for param in params:
        if param.get("name") == name:
            value = param.get("value")
            # Handle array format: value is ["string"]
            if isinstance(value, list) and len(value) > 0:
                value = value[0]
            if isinstance(value, str):
                return value
    return None


def _transform_schedule_entries(
    schedule: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    """Transform schedule entries to add type_name and UTC timestamps."""
    if schedule is None:
        return None
    result = []
    for entry in schedule:
        transformed = dict(entry)
        # Add human-readable type name
        type_id = entry.get("type")
        if type_id is not None:
            transformed["type_name"] = SCHEDULE_CONTROL_MODES.get(type_id, f"unknown_{type_id}")
        # Add UTC timestamps
        from_ts = entry.get("from")
        if from_ts is not None:
            transformed["from_utc"] = datetime.fromtimestamp(from_ts, tz=UTC).isoformat()
        to_ts = entry.get("to")
        if to_ts is not None:
            transformed["to_utc"] = datetime.fromtimestamp(to_ts, tz=UTC).isoformat()
        result.append(transformed)
    return result


@dataclass(frozen=True, kw_only=True)
class HomevoltSensorEntityDescription(SensorEntityDescription):
    """Describes a Homevolt sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any]
    data_key: str = "ems"
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None
    device_type: DeviceType = DeviceType.ECU


# EMS Sensors (Energy Management System)
# Supports both nested format (ems[0].ems_data.*) and flat format (battery_soc, etc.)
EMS_SENSORS: tuple[HomevoltSensorEntityDescription, ...] = (
    # Battery SOC - nested: ems_data.soc_avg (centi-%) or bms_data[0].soc, flat: battery_soc
    HomevoltSensorEntityDescription(
        key="battery_soc",
        translation_key="battery_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        device_type=DeviceType.CLUSTER,
        value_fn=lambda data: (
            _centi_to_unit(_get_ems_data(data).get("soc_avg"))
            or _get_first_bms(data).get("soc")
            or data.get("battery_soc")  # OpenAPI flat format
        ),
    ),
    # Inverter power - nested: ems_data.power, flat: inverter_power
    HomevoltSensorEntityDescription(
        key="inverter_power",
        translation_key="inverter_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        device_type=DeviceType.CLUSTER,
        value_fn=lambda data: (
            _get_ems_data(data).get("power") or data.get("inverter_power")  # OpenAPI flat format
        ),
    ),
    # Inverter energy produced - API returns Wh, convert to kWh
    HomevoltSensorEntityDescription(
        key="inverter_energy_produced",
        translation_key="inverter_energy_produced",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_type=DeviceType.CLUSTER,
        value_fn=lambda data: _milli_to_unit(_get_ems_data(data).get("energy_produced")),
    ),
    # Inverter energy consumed - API returns Wh, convert to kWh
    HomevoltSensorEntityDescription(
        key="inverter_energy_consumed",
        translation_key="inverter_energy_consumed",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_type=DeviceType.CLUSTER,
        value_fn=lambda data: _milli_to_unit(_get_ems_data(data).get("energy_consumed")),
    ),
    # EMS frequency - nested: milli-Hz (÷1000), flat: grid_frequency in Hz
    HomevoltSensorEntityDescription(
        key="ems_frequency",
        translation_key="ems_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        device_type=DeviceType.CLUSTER,
        value_fn=lambda data: (
            _milli_to_unit(_get_ems_data(data).get("frequency"))
            or data.get("grid_frequency")  # OpenAPI flat format (already Hz)
        ),
    ),
    # System temperature - API returns deci-degrees (ECU-specific)
    HomevoltSensorEntityDescription(
        key="system_temperature",
        translation_key="system_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        device_type=DeviceType.ECU,
        value_fn=lambda data: _deci_to_unit(_get_ems_data(data).get("sys_temp")),
    ),
    # Available capacity
    HomevoltSensorEntityDescription(
        key="available_capacity",
        translation_key="available_capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_type=DeviceType.CLUSTER,
        value_fn=lambda data: _get_ems_data(data).get("avail_cap"),
    ),
    # Operation state - nested: op_state_str, flat: ems_state (OpenAPI)
    HomevoltSensorEntityDescription(
        key="operation_state",
        translation_key="operation_state",
        device_type=DeviceType.CLUSTER,
        value_fn=lambda data: (
            _get_first_ems(data).get("op_state_str") or data.get("ems_state")  # OpenAPI flat format
        ),
    ),
    # Battery state - nested: ems_data.state_str
    HomevoltSensorEntityDescription(
        key="battery_state",
        translation_key="battery_state",
        device_type=DeviceType.CLUSTER,
        value_fn=lambda data: _get_ems_data(data).get("state_str"),
    ),
    # Firmware version - from local EMS entry (where ecu_host is empty)
    HomevoltSensorEntityDescription(
        key="firmware_version",
        translation_key="firmware_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_type=DeviceType.ECU,
        value_fn=lambda data: _get_local_ems(data).get("ems_info", {}).get("fw_version"),
    ),
    # Alarm messages - length of alarm_str list from local EMS entry
    HomevoltSensorEntityDescription(
        key="alarm_messages",
        translation_key="alarm_messages",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_type=DeviceType.ECU,
        value_fn=lambda data: _list_length_or_none(
            _get_local_ems(data).get("ems_data", {}).get("alarm_str")
        ),
        attributes_fn=lambda data: {
            "messages": _get_local_ems(data).get("ems_data", {}).get("alarm_str"),
        },
    ),
    # Warning messages - length of warning_str list from local EMS entry
    HomevoltSensorEntityDescription(
        key="warning_messages",
        translation_key="warning_messages",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_type=DeviceType.ECU,
        value_fn=lambda data: _list_length_or_none(
            _get_local_ems(data).get("ems_data", {}).get("warning_str")
        ),
        attributes_fn=lambda data: {
            "messages": _get_local_ems(data).get("ems_data", {}).get("warning_str"),
        },
    ),
    # Info messages - length of info_str list from local EMS entry
    HomevoltSensorEntityDescription(
        key="info_messages",
        translation_key="info_messages",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_type=DeviceType.ECU,
        value_fn=lambda data: _list_length_or_none(
            _get_local_ems(data).get("ems_data", {}).get("info_str")
        ),
        attributes_fn=lambda data: {
            "messages": _get_local_ems(data).get("ems_data", {}).get("info_str"),
        },
    ),
    # Rated power from individual ECU's ems_info
    HomevoltSensorEntityDescription(
        key="rated_power",
        translation_key="rated_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="ems",
        device_type=DeviceType.ECU,
        value_fn=lambda data: _get_first_ems_info(data).get("rated_power"),
    ),
    # EMS Prediction sensors
    HomevoltSensorEntityDescription(
        key="avail_charge_power",
        translation_key="avail_charge_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        device_type=DeviceType.CLUSTER,
        value_fn=lambda data: _get_ems_prediction(data).get("avail_ch_pwr"),
    ),
    HomevoltSensorEntityDescription(
        key="avail_discharge_power",
        translation_key="avail_discharge_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        device_type=DeviceType.CLUSTER,
        value_fn=lambda data: _get_ems_prediction(data).get("avail_di_pwr"),
    ),
    HomevoltSensorEntityDescription(
        key="avail_charge_energy",
        translation_key="avail_charge_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_type=DeviceType.CLUSTER,
        value_fn=lambda data: _get_ems_prediction(data).get("avail_ch_energy"),
    ),
    HomevoltSensorEntityDescription(
        key="avail_discharge_energy",
        translation_key="avail_discharge_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_type=DeviceType.CLUSTER,
        value_fn=lambda data: _get_ems_prediction(data).get("avail_di_energy"),
    ),
    HomevoltSensorEntityDescription(
        key="avail_inverter_charge_power",
        translation_key="avail_inverter_charge_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        device_type=DeviceType.CLUSTER,
        value_fn=lambda data: _get_ems_prediction(data).get("avail_inv_ch_pwr"),
    ),
    HomevoltSensorEntityDescription(
        key="avail_inverter_discharge_power",
        translation_key="avail_inverter_discharge_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        device_type=DeviceType.CLUSTER,
        value_fn=lambda data: _get_ems_prediction(data).get("avail_inv_di_pwr"),
    ),
)

# Mains Sensors - supports both actual API and OpenAPI field names (ECU-specific)
MAINS_SENSORS: tuple[HomevoltSensorEntityDescription, ...] = (
    HomevoltSensorEntityDescription(
        key="mains_voltage",
        translation_key="mains_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        data_key="mains",
        device_type=DeviceType.ECU,
        value_fn=lambda data: data.get("mains_voltage_rms"),
    ),
    HomevoltSensorEntityDescription(
        key="mains_frequency",
        translation_key="mains_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        data_key="mains",
        device_type=DeviceType.ECU,
        value_fn=lambda data: data.get("frequency"),
    ),
)

# Status Sensors (Diagnostic) - supports both actual API and OpenAPI field names (ECU-specific)
STATUS_SENSORS: tuple[HomevoltSensorEntityDescription, ...] = (
    HomevoltSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        data_key="status",
        device_type=DeviceType.ECU,
        # up_time is always present in status.json (in ms, convert to days)
        value_fn=lambda data: data.get("up_time", 0) / 86400000,
    ),
    HomevoltSensorEntityDescription(
        key="wifi_rssi",
        translation_key="wifi_rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="status",
        device_type=DeviceType.ECU,
        value_fn=lambda data: data.get("wifi_status", {}).get("rssi"),
    ),
    HomevoltSensorEntityDescription(
        key="lte_rssi",
        translation_key="lte_rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="status",
        device_type=DeviceType.ECU,
        value_fn=lambda data: data.get("lte_status", {}).get("rssi"),
    ),
)

# Schedule Sensors (ECU - schedule data comes from each ECU's API)
SCHEDULE_SENSORS: tuple[HomevoltSensorEntityDescription, ...] = (
    HomevoltSensorEntityDescription(
        key="schedule_mode",
        translation_key="schedule_mode",
        data_key="schedule",
        device_type=DeviceType.ECU,
        value_fn=lambda data: "local" if data.get("local_mode") else "remote",
        attributes_fn=lambda data: {
            "schedule_id": data.get("schedule_id"),
            "schedule": _transform_schedule_entries(data.get("schedule")),
        },
    ),
)

# EMS Mode Sensor (ECU-specific - shows role of this ECU in the cluster)
EMS_MODE_SENSORS: tuple[HomevoltSensorEntityDescription, ...] = (
    HomevoltSensorEntityDescription(
        key="ems_mode",
        translation_key="ems_mode",
        data_key="ems",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_type=DeviceType.ECU,
        # leader when ems list has more than one unit (can see other devices in cluster)
        value_fn=lambda data: (
            "leader"
            if isinstance(data, dict)
            and isinstance(data.get("ems"), list)
            and len(data.get("ems", [])) > 1
            else "follower"
        ),
    ),
)

# OTA Sensors (from ota_manifest.json)
OTA_SENSORS: tuple[HomevoltSensorEntityDescription, ...] = (
    HomevoltSensorEntityDescription(
        key="ota_version",
        translation_key="ota_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="ota_manifest",
        device_type=DeviceType.ECU,
        value_fn=lambda data: data.get("version"),
    ),
)

# External Sensor Sensors (Grid, Solar, Load from sensors array in ems.json)
# These sensors read from the sensors array at the top level of ems.json response
EXTERNAL_SENSOR_SENSORS: tuple[HomevoltSensorEntityDescription, ...] = (
    # Grid sensors
    HomevoltSensorEntityDescription(
        key="grid_power",
        translation_key="grid_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        data_key="ems",
        device_type=DeviceType.ECU,
        value_fn=lambda data: _get_sensor_by_type(data, "grid").get("total_power"),
    ),
    HomevoltSensorEntityDescription(
        key="grid_energy_imported",
        translation_key="grid_energy_imported",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        data_key="ems",
        device_type=DeviceType.ECU,
        value_fn=lambda data: _get_sensor_by_type(data, "grid").get("energy_imported"),
    ),
    HomevoltSensorEntityDescription(
        key="grid_energy_exported",
        translation_key="grid_energy_exported",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        data_key="ems",
        device_type=DeviceType.ECU,
        value_fn=lambda data: _get_sensor_by_type(data, "grid").get("energy_exported"),
    ),
    HomevoltSensorEntityDescription(
        key="grid_rssi",
        translation_key="grid_rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="ems",
        device_type=DeviceType.ECU,
        value_fn=lambda data: _get_sensor_by_type(data, "grid").get("rssi"),
    ),
    # Solar sensors
    HomevoltSensorEntityDescription(
        key="solar_power",
        translation_key="solar_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        data_key="ems",
        device_type=DeviceType.ECU,
        value_fn=lambda data: _get_sensor_by_type(data, "solar").get("total_power"),
    ),
    HomevoltSensorEntityDescription(
        key="solar_energy_imported",
        translation_key="solar_energy_imported",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        data_key="ems",
        device_type=DeviceType.ECU,
        value_fn=lambda data: _get_sensor_by_type(data, "solar").get("energy_imported"),
    ),
    HomevoltSensorEntityDescription(
        key="solar_energy_exported",
        translation_key="solar_energy_exported",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        data_key="ems",
        device_type=DeviceType.ECU,
        value_fn=lambda data: _get_sensor_by_type(data, "solar").get("energy_exported"),
    ),
    HomevoltSensorEntityDescription(
        key="solar_rssi",
        translation_key="solar_rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="ems",
        device_type=DeviceType.ECU,
        value_fn=lambda data: _get_sensor_by_type(data, "solar").get("rssi"),
    ),
    # Load sensors
    HomevoltSensorEntityDescription(
        key="load_power",
        translation_key="load_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        data_key="ems",
        device_type=DeviceType.ECU,
        value_fn=lambda data: _get_sensor_by_type(data, "load").get("total_power"),
    ),
    HomevoltSensorEntityDescription(
        key="load_energy_imported",
        translation_key="load_energy_imported",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        data_key="ems",
        device_type=DeviceType.ECU,
        value_fn=lambda data: _get_sensor_by_type(data, "load").get("energy_imported"),
    ),
    HomevoltSensorEntityDescription(
        key="load_energy_exported",
        translation_key="load_energy_exported",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        data_key="ems",
        device_type=DeviceType.ECU,
        value_fn=lambda data: _get_sensor_by_type(data, "load").get("energy_exported"),
    ),
    HomevoltSensorEntityDescription(
        key="load_rssi",
        translation_key="load_rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        data_key="ems",
        device_type=DeviceType.ECU,
        value_fn=lambda data: _get_sensor_by_type(data, "load").get("rssi"),
    ),
)

# Cluster-only sensors (only available on cluster device, from aggregated data)
CLUSTER_ONLY_SENSORS: tuple[HomevoltSensorEntityDescription, ...] = (
    # Rated power from aggregated.ems_info
    # Note: _get_data() wraps aggregated in ems[0], so use _get_first_ems_info
    HomevoltSensorEntityDescription(
        key="rated_power",
        translation_key="rated_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        data_key="ems",
        device_type=DeviceType.CLUSTER,
        value_fn=lambda data: _get_first_ems_info(data).get("rated_power"),
    ),
)

ALL_SENSORS = (
    EMS_SENSORS
    + MAINS_SENSORS
    + STATUS_SENSORS
    + SCHEDULE_SENSORS
    + EMS_MODE_SENSORS
    + OTA_SENSORS
    + EXTERNAL_SENSOR_SENSORS
)


def _has_external_sensor(coordinator: HomevoltCoordinator, sensor_type: str) -> bool:
    """Check if an external sensor type is present in the device data."""
    ems_data = coordinator.data.get("ems", {})
    if not isinstance(ems_data, dict):
        return False
    sensors = ems_data.get("sensors", [])
    if not isinstance(sensors, list):
        return False
    return any(
        isinstance(sensor, dict) and sensor.get("type") == sensor_type
        for sensor in sensors
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomevoltConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homevolt sensors based on a config entry."""
    coordinator = entry.runtime_data

    entities: list[HomevoltSensor] = []

    # Determine which external sensor types are available
    has_grid = _has_external_sensor(coordinator, "grid")
    has_solar = _has_external_sensor(coordinator, "solar")
    has_load = _has_external_sensor(coordinator, "load")

    # Map sensor keys to their availability
    external_sensor_availability = {
        "grid_power": has_grid,
        "grid_energy_imported": has_grid,
        "grid_energy_exported": has_grid,
        "grid_rssi": has_grid,
        "solar_power": has_solar,
        "solar_energy_imported": has_solar,
        "solar_energy_exported": has_solar,
        "solar_rssi": has_solar,
        "load_power": has_load,
        "load_energy_imported": has_load,
        "load_energy_exported": has_load,
        "load_rssi": has_load,
    }

    for description in ALL_SENSORS:
        # Skip external sensors that aren't available on this device
        if description.key in external_sensor_availability:
            if not external_sensor_availability[description.key]:
                continue

        # ECU device gets all available sensors with individual data
        entities.append(HomevoltSensor(coordinator, description, DeviceType.ECU))

        # Leader also gets cluster sensors with aggregated data
        if coordinator.is_leader and description.device_type == DeviceType.CLUSTER:
            entities.append(HomevoltSensor(coordinator, description, DeviceType.CLUSTER))

    # Cluster-only sensors (only on cluster device, not ECU)
    if coordinator.is_leader:
        for description in CLUSTER_ONLY_SENSORS:
            entities.append(HomevoltSensor(coordinator, description, DeviceType.CLUSTER))

    async_add_entities(entities)


class HomevoltSensor(CoordinatorEntity[HomevoltCoordinator], SensorEntity):
    """Representation of a Homevolt sensor."""

    entity_description: HomevoltSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        description: HomevoltSensorEntityDescription,
        device_type: DeviceType,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_type = device_type

        if device_type == DeviceType.CLUSTER:
            self._attr_unique_id = f"{coordinator.cluster_id}_{description.key}"
            self._attr_device_info = get_cluster_device_info(coordinator)
        else:
            self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
            self._attr_device_info = get_ecu_device_info(coordinator)

    def _get_data(self) -> dict[str, Any]:
        """Get data for this sensor, using aggregated data for cluster sensors."""
        raw_data = self.coordinator.data.get(self.entity_description.data_key, {})
        data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}

        # For cluster sensors using EMS data, always use aggregated data
        # No fallback to individual units - prevents inconsistent values when ems order changes
        if self._device_type == DeviceType.CLUSTER and self.entity_description.data_key == "ems":
            # Wrap aggregated data in ems list so _get_first_ems/_get_ems_data work correctly
            # If aggregated is missing, use empty dict - sensors will return unavailable
            # Preserve sensors array at top level for external sensor access
            aggregated = data.get("aggregated", {})
            sensors = data.get("sensors", [])
            data = {"ems": [aggregated], "sensors": sensors}

        return data

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._get_data())

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self._get_data())
