"""Tests for Homevolt Local sensor platform."""

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
)

from custom_components.homevolt_local.device import DeviceType
from custom_components.homevolt_local.sensor import (
    ALL_SENSORS,
    CLUSTER_ONLY_SENSORS,
    EMS_MODE_SENSORS,
    EMS_SENSORS,
    EXTERNAL_SENSOR_SENSORS,
    MAINS_SENSORS,
    OTA_SENSORS,
    PARALLEL_UPDATES,
    SCHEDULE_CONTROL_MODES,
    SCHEDULE_SENSORS,
    STATUS_SENSORS,
    _deci_to_unit,
    _get_aggregated_ems_info,
    _get_ems_data,
    _get_ems_prediction,
    _get_first_bms,
    _get_first_ems,
    _get_first_ems_info,
    _get_param_string,
    _get_sensor_by_type,
    _milli_to_unit,
    _transform_schedule_entries,
)


class TestUnitConversions:
    """Test unit conversion functions."""

    def test_deci_to_unit_positive(self) -> None:
        """Test deci to unit conversion with positive value."""
        assert _deci_to_unit(250) == 25.0

    def test_deci_to_unit_zero(self) -> None:
        """Test deci to unit conversion with zero."""
        assert _deci_to_unit(0) == 0.0

    def test_deci_to_unit_negative(self) -> None:
        """Test deci to unit conversion with negative value."""
        assert _deci_to_unit(-100) == -10.0

    def test_deci_to_unit_none(self) -> None:
        """Test deci to unit conversion with None."""
        assert _deci_to_unit(None) is None

    def test_milli_to_unit_positive(self) -> None:
        """Test milli to unit conversion with positive value."""
        assert _milli_to_unit(50000) == 50.0

    def test_milli_to_unit_zero(self) -> None:
        """Test milli to unit conversion with zero."""
        assert _milli_to_unit(0) == 0.0

    def test_milli_to_unit_none(self) -> None:
        """Test milli to unit conversion with None."""
        assert _milli_to_unit(None) is None


class TestDataExtractors:
    """Test data extraction helper functions."""

    def test_get_first_ems_nested_format(self) -> None:
        """Test extracting first EMS from nested format."""
        data = {"ems": [{"ecu_id": "test1"}, {"ecu_id": "test2"}]}
        result = _get_first_ems(data)
        assert result == {"ecu_id": "test1"}

    def test_get_first_ems_empty_list(self) -> None:
        """Test extracting first EMS from empty list."""
        data = {"ems": []}
        result = _get_first_ems(data)
        assert result == {}

    def test_get_first_ems_missing_key(self) -> None:
        """Test extracting first EMS when key is missing."""
        data = {}
        result = _get_first_ems(data)
        assert result == {}

    def test_get_first_ems_not_list(self) -> None:
        """Test extracting first EMS when value is not a list."""
        data = {"ems": {"single": "value"}}
        result = _get_first_ems(data)
        assert result == {}

    def test_get_ems_data(self) -> None:
        """Test extracting EMS data from first EMS unit."""
        data = {"ems": [{"ems_data": {"soc_avg": 75, "power": 1500}}]}
        result = _get_ems_data(data)
        assert result == {"soc_avg": 75, "power": 1500}

    def test_get_ems_data_missing(self) -> None:
        """Test extracting EMS data when missing."""
        data = {"ems": [{}]}
        result = _get_ems_data(data)
        assert result == {}

    def test_get_first_bms(self) -> None:
        """Test extracting first BMS data."""
        data = {"ems": [{"bms_data": [{"soc": 75}, {"soc": 80}]}]}
        result = _get_first_bms(data)
        assert result == {"soc": 75}

    def test_get_first_bms_empty(self) -> None:
        """Test extracting first BMS when empty."""
        data = {"ems": [{"bms_data": []}]}
        result = _get_first_bms(data)
        assert result == {}

    def test_get_first_ems_info(self) -> None:
        """Test extracting ems_info from first EMS unit."""
        data = {
            "ems": [
                {"ecu_id": "test1", "ems_info": {"capacity": 10000, "rated_power": 2500}},
                {"ecu_id": "test2", "ems_info": {"capacity": 10000, "rated_power": 2500}},
            ]
        }
        result = _get_first_ems_info(data)
        assert result == {"capacity": 10000, "rated_power": 2500}

    def test_get_first_ems_info_missing_ems_info(self) -> None:
        """Test extracting ems_info when ems_info is missing from first EMS."""
        data = {"ems": [{"ecu_id": "test1"}]}
        result = _get_first_ems_info(data)
        assert result == {}

    def test_get_first_ems_info_empty_ems_list(self) -> None:
        """Test extracting ems_info when ems list is empty."""
        data = {"ems": []}
        result = _get_first_ems_info(data)
        assert result == {}

    def test_get_aggregated_ems_info(self) -> None:
        """Test extracting aggregated ems_info."""
        data = {"aggregated": {"ems_info": {"rated_capacity": 20000, "rated_power": 5000}}}
        result = _get_aggregated_ems_info(data)
        assert result == {"rated_capacity": 20000, "rated_power": 5000}

    def test_get_aggregated_ems_info_missing_aggregated(self) -> None:
        """Test extracting aggregated ems_info when aggregated is missing."""
        data = {"ems": [{"ecu_id": "test"}]}
        result = _get_aggregated_ems_info(data)
        assert result == {}

    def test_get_aggregated_ems_info_missing_ems_info(self) -> None:
        """Test extracting aggregated ems_info when ems_info is missing."""
        data = {"aggregated": {}}
        result = _get_aggregated_ems_info(data)
        assert result == {}

    def test_get_aggregated_ems_info_not_dict(self) -> None:
        """Test extracting aggregated ems_info when aggregated is not a dict."""
        data = {"aggregated": "invalid"}
        result = _get_aggregated_ems_info(data)
        assert result == {}

    def test_get_ems_prediction(self) -> None:
        """Test extracting ems_prediction from first EMS unit."""
        data = {
            "ems": [
                {
                    "ecu_id": "test1",
                    "ems_prediction": {
                        "avail_ch_pwr": 5000,
                        "avail_di_pwr": 4500,
                    },
                }
            ]
        }
        result = _get_ems_prediction(data)
        assert result == {"avail_ch_pwr": 5000, "avail_di_pwr": 4500}

    def test_get_ems_prediction_missing(self) -> None:
        """Test extracting ems_prediction when missing from first EMS."""
        data = {"ems": [{"ecu_id": "test1"}]}
        result = _get_ems_prediction(data)
        assert result == {}

    def test_get_ems_prediction_empty_ems_list(self) -> None:
        """Test extracting ems_prediction when ems list is empty."""
        data = {"ems": []}
        result = _get_ems_prediction(data)
        assert result == {}


class TestSensorDescriptions:
    """Test sensor entity descriptions."""

    def test_parallel_updates_constant(self) -> None:
        """Test PARALLEL_UPDATES is set to 1."""
        assert PARALLEL_UPDATES == 1

    def test_all_sensors_combined(self) -> None:
        """Test ALL_SENSORS combines all sensor groups."""
        expected = (
            len(EMS_SENSORS)
            + len(MAINS_SENSORS)
            + len(STATUS_SENSORS)
            + len(SCHEDULE_SENSORS)
            + len(EMS_MODE_SENSORS)
            + len(OTA_SENSORS)
            + len(EXTERNAL_SENSOR_SENSORS)
        )
        assert len(ALL_SENSORS) == expected

    def test_battery_soc_sensor(self) -> None:
        """Test battery SOC sensor description."""
        sensor = next(s for s in EMS_SENSORS if s.key == "battery_soc")
        assert sensor.native_unit_of_measurement == PERCENTAGE
        assert sensor.device_class == SensorDeviceClass.BATTERY
        assert sensor.state_class == SensorStateClass.MEASUREMENT
        assert sensor.suggested_display_precision == 1

    def test_inverter_power_sensor(self) -> None:
        """Test inverter power sensor description."""
        sensor = next(s for s in EMS_SENSORS if s.key == "inverter_power")
        assert sensor.native_unit_of_measurement == UnitOfPower.WATT
        assert sensor.device_class == SensorDeviceClass.POWER

    def test_system_temperature_is_regular_sensor(self) -> None:
        """Test system temperature is a regular sensor (not diagnostic)."""
        sensor = next(s for s in EMS_SENSORS if s.key == "system_temperature")
        assert sensor.entity_category is None

    def test_uptime_is_diagnostic(self) -> None:
        """Test uptime is a diagnostic sensor."""
        sensor = next(s for s in STATUS_SENSORS if s.key == "uptime")
        assert sensor.entity_category == EntityCategory.DIAGNOSTIC
        assert sensor.entity_registry_enabled_default is False

    def test_mains_voltage_sensor(self) -> None:
        """Test mains voltage sensor description."""
        sensor = next(s for s in MAINS_SENSORS if s.key == "mains_voltage")
        assert sensor.native_unit_of_measurement == UnitOfElectricPotential.VOLT
        assert sensor.device_class == SensorDeviceClass.VOLTAGE
        assert sensor.data_key == "mains"
        assert sensor.entity_registry_enabled_default is False

    def test_mains_frequency_sensor(self) -> None:
        """Test mains frequency sensor description."""
        sensor = next(s for s in MAINS_SENSORS if s.key == "mains_frequency")
        assert sensor.native_unit_of_measurement == UnitOfFrequency.HERTZ
        assert sensor.device_class == SensorDeviceClass.FREQUENCY
        assert sensor.data_key == "mains"
        assert sensor.entity_registry_enabled_default is False

    def test_energy_sensors_total_increasing(self) -> None:
        """Test energy sensors have TOTAL_INCREASING state class."""
        energy_sensors = [
            s
            for s in EMS_SENSORS
            if s.key in ("inverter_energy_produced", "inverter_energy_consumed")
        ]
        for sensor in energy_sensors:
            assert sensor.state_class == SensorStateClass.TOTAL_INCREASING
            assert sensor.device_class == SensorDeviceClass.ENERGY


class TestSensorValueFunctions:
    """Test sensor value extraction functions."""

    def test_battery_soc_nested_format(self, mock_ems_data: dict) -> None:
        """Test battery SOC extraction from nested format."""
        sensor = next(s for s in EMS_SENSORS if s.key == "battery_soc")
        result = sensor.value_fn(mock_ems_data)
        assert result == 75

    def test_battery_soc_flat_format(self) -> None:
        """Test battery SOC extraction from flat format."""
        sensor = next(s for s in EMS_SENSORS if s.key == "battery_soc")
        data = {"battery_soc": 80}
        result = sensor.value_fn(data)
        assert result == 80

    def test_battery_soc_from_bms(self) -> None:
        """Test battery SOC extraction from BMS data."""
        sensor = next(s for s in EMS_SENSORS if s.key == "battery_soc")
        data = {
            "ems": [
                {
                    "ems_data": {},  # No soc_avg
                    "bms_data": [{"soc": 65}],
                }
            ]
        }
        result = sensor.value_fn(data)
        assert result == 65

    def test_inverter_power_nested(self, mock_ems_data: dict) -> None:
        """Test inverter power extraction from nested format."""
        sensor = next(s for s in EMS_SENSORS if s.key == "inverter_power")
        result = sensor.value_fn(mock_ems_data)
        assert result == 1500

    def test_inverter_power_flat(self) -> None:
        """Test inverter power extraction from flat format."""
        sensor = next(s for s in EMS_SENSORS if s.key == "inverter_power")
        data = {"inverter_power": 2000}
        result = sensor.value_fn(data)
        assert result == 2000

    def test_ems_frequency_nested_milli_hz(self, mock_ems_data: dict) -> None:
        """Test EMS frequency conversion from milli-Hz."""
        sensor = next(s for s in EMS_SENSORS if s.key == "ems_frequency")
        result = sensor.value_fn(mock_ems_data)
        assert result == 50.0  # 50000 mHz = 50 Hz

    def test_ems_frequency_flat_hz(self) -> None:
        """Test EMS frequency from flat format (already Hz)."""
        sensor = next(s for s in EMS_SENSORS if s.key == "ems_frequency")
        data = {"grid_frequency": 49.95}
        result = sensor.value_fn(data)
        assert result == 49.95

    def test_system_temperature_conversion(self, mock_ems_data: dict) -> None:
        """Test system temperature conversion from deci-degrees."""
        sensor = next(s for s in EMS_SENSORS if s.key == "system_temperature")
        result = sensor.value_fn(mock_ems_data)
        assert result == 25.0  # 250 deci-C = 25 C

    def test_operation_state_nested(self, mock_ems_data: dict) -> None:
        """Test operation state from nested format."""
        sensor = next(s for s in EMS_SENSORS if s.key == "operation_state")
        result = sensor.value_fn(mock_ems_data)
        assert result == "IDLE"

    def test_operation_state_flat(self) -> None:
        """Test operation state from flat format."""
        sensor = next(s for s in EMS_SENSORS if s.key == "operation_state")
        data = {"ems_state": "CHARGING"}
        result = sensor.value_fn(data)
        assert result == "CHARGING"

    def test_battery_state(self, mock_ems_data: dict) -> None:
        """Test battery state extraction from ems_data.state_str."""
        sensor = next(s for s in EMS_SENSORS if s.key == "battery_state")
        result = sensor.value_fn(mock_ems_data)
        assert result == "discharging"

    def test_battery_state_missing(self) -> None:
        """Test battery state returns None when state_str is missing."""
        sensor = next(s for s in EMS_SENSORS if s.key == "battery_state")
        data = {"ems": [{"ems_data": {}}]}
        result = sensor.value_fn(data)
        assert result is None

    def test_alarm_messages(self) -> None:
        """Test alarm messages is length of alarm_str list."""
        sensor = next(s for s in EMS_SENSORS if s.key == "alarm_messages")
        data = {
            "ems": [
                {
                    "ecu_host": "",  # Local ECU
                    "ems_data": {
                        "alarm_str": ["Battery overtemp", "Grid fault"],
                    },
                }
            ]
        }
        result = sensor.value_fn(data)
        assert result == 2
        attrs = sensor.attributes_fn(data)
        assert attrs == {"messages": ["Battery overtemp", "Grid fault"]}

    def test_alarm_messages_not_list(self) -> None:
        """Test alarm messages returns None when alarm_str is not a list."""
        sensor = next(s for s in EMS_SENSORS if s.key == "alarm_messages")
        data = {
            "ems": [
                {
                    "ecu_host": "",
                    "ems_data": {
                        "alarm_str": "not a list",
                    },
                }
            ]
        }
        result = sensor.value_fn(data)
        assert result is None

    def test_alarm_messages_empty(self) -> None:
        """Test alarm messages when no alarms present."""
        sensor = next(s for s in EMS_SENSORS if s.key == "alarm_messages")
        data = {
            "ems": [
                {
                    "ecu_host": "",
                    "ems_data": {
                        "alarm_str": [],
                    },
                }
            ]
        }
        result = sensor.value_fn(data)
        assert result == 0

    def test_warning_messages(self) -> None:
        """Test warning messages is length of warning_str list."""
        sensor = next(s for s in EMS_SENSORS if s.key == "warning_messages")
        data = {
            "ems": [
                {
                    "ecu_host": "",
                    "ems_data": {
                        "warning_str": ["Low battery"],
                    },
                }
            ]
        }
        result = sensor.value_fn(data)
        assert result == 1
        attrs = sensor.attributes_fn(data)
        assert attrs == {"messages": ["Low battery"]}

    def test_info_messages(self) -> None:
        """Test info messages is length of info_str list."""
        sensor = next(s for s in EMS_SENSORS if s.key == "info_messages")
        data = {
            "ems": [
                {
                    "ecu_host": "",
                    "ems_data": {
                        "info_str": ["Charging", "Grid connected", "System ready"],
                    },
                }
            ]
        }
        result = sensor.value_fn(data)
        assert result == 3
        attrs = sensor.attributes_fn(data)
        assert attrs == {"messages": ["Charging", "Grid connected", "System ready"]}

    def test_uptime(self, mock_status_data: dict) -> None:
        """Test uptime conversion from ms to days."""
        sensor = next(s for s in STATUS_SENSORS if s.key == "uptime")
        result = sensor.value_fn(mock_status_data)
        # 123456789 ms / 86400000 ms per day ≈ 1.429 days
        assert result == pytest.approx(123456789 / 86400000)

    def test_uptime_zero_value(self) -> None:
        """Test uptime handles zero correctly (device just rebooted)."""
        sensor = next(s for s in STATUS_SENSORS if s.key == "uptime")
        data = {"up_time": 0}
        result = sensor.value_fn(data)
        assert result == 0.0

    def test_mains_voltage(self, mock_mains_data: dict) -> None:
        """Test mains voltage extraction."""
        sensor = next(s for s in MAINS_SENSORS if s.key == "mains_voltage")
        result = sensor.value_fn(mock_mains_data)
        assert result == 230.5

    def test_mains_frequency(self, mock_mains_data: dict) -> None:
        """Test mains frequency extraction."""
        sensor = next(s for s in MAINS_SENSORS if s.key == "mains_frequency")
        result = sensor.value_fn(mock_mains_data)
        assert result == 50.01

    def test_energy_produced_conversion(self) -> None:
        """Test energy produced conversion from Wh to kWh."""
        sensor = next(s for s in EMS_SENSORS if s.key == "inverter_energy_produced")
        data = {
            "ems": [{"ems_data": {"energy_produced": 10000000}}]  # 10000 Wh
        }
        result = sensor.value_fn(data)
        assert result == 10000.0  # kWh

    def test_energy_consumed_conversion(self) -> None:
        """Test energy consumed conversion from Wh to kWh."""
        sensor = next(s for s in EMS_SENSORS if s.key == "inverter_energy_consumed")
        data = {
            "ems": [{"ems_data": {"energy_consumed": 8000000}}]  # 8000 Wh
        }
        result = sensor.value_fn(data)
        assert result == 8000.0  # kWh


class TestScheduleSensorValueFunctions:
    """Test schedule sensor value extraction functions."""

    def test_schedule_mode_local(self, mock_schedule_data: dict) -> None:
        """Test schedule mode returns 'local' when local_mode is True."""
        sensor = next(s for s in SCHEDULE_SENSORS if s.key == "schedule_mode")
        result = sensor.value_fn(mock_schedule_data)
        assert result == "local"

    def test_schedule_mode_remote(self) -> None:
        """Test schedule mode returns 'remote' when local_mode is False."""
        sensor = next(s for s in SCHEDULE_SENSORS if s.key == "schedule_mode")
        data = {"local_mode": False, "schedule_id": "test-123", "schedule": []}
        result = sensor.value_fn(data)
        assert result == "remote"

    def test_schedule_mode_attributes(self, mock_schedule_data: dict) -> None:
        """Test schedule mode extra attributes."""
        sensor = next(s for s in SCHEDULE_SENSORS if s.key == "schedule_mode")
        result = sensor.attributes_fn(mock_schedule_data)
        assert result["schedule_id"] == "test-schedule-123"
        assert len(result["schedule"]) == 1
        assert result["schedule"][0]["id"] == 1
        # Verify transformed fields are present
        assert result["schedule"][0]["type_name"] == "inverter_charge"
        assert "from_utc" in result["schedule"][0]
        assert "to_utc" in result["schedule"][0]

    def test_schedule_mode_attributes_with_type_name(self) -> None:
        """Test schedule entries include type_name."""
        sensor = next(s for s in SCHEDULE_SENSORS if s.key == "schedule_mode")
        data = {
            "local_mode": True,
            "schedule_id": "test-123",
            "schedule": [
                {"id": 1, "from": 1766131200, "to": 1766132100, "type": 1, "params": {}},
                {"id": 2, "from": 1766132100, "to": 1766133000, "type": 3, "params": {}},
            ],
        }
        result = sensor.attributes_fn(data)
        assert result["schedule"][0]["type_name"] == "inverter_charge"
        assert result["schedule"][1]["type_name"] == "grid_charge"

    def test_schedule_mode_attributes_with_utc_times(self) -> None:
        """Test schedule entries include from_utc and to_utc."""
        sensor = next(s for s in SCHEDULE_SENSORS if s.key == "schedule_mode")
        data = {
            "local_mode": True,
            "schedule_id": "test-123",
            "schedule": [
                {"id": 1, "from": 1766131200, "to": 1766132100, "type": 1, "params": {}},
            ],
        }
        result = sensor.attributes_fn(data)
        assert "from_utc" in result["schedule"][0]
        assert "to_utc" in result["schedule"][0]
        # Verify ISO format (1766131200 = 2025-12-19T08:00:00 UTC)
        assert result["schedule"][0]["from_utc"] == "2025-12-19T08:00:00+00:00"
        assert result["schedule"][0]["to_utc"] == "2025-12-19T08:15:00+00:00"

    def test_schedule_mode_attributes_unknown_type(self) -> None:
        """Test schedule entries with unknown type get fallback name."""
        sensor = next(s for s in SCHEDULE_SENSORS if s.key == "schedule_mode")
        data = {
            "local_mode": True,
            "schedule_id": "test-123",
            "schedule": [
                {"id": 1, "from": 1766131200, "to": 1766132100, "type": 99, "params": {}},
            ],
        }
        result = sensor.attributes_fn(data)
        assert result["schedule"][0]["type_name"] == "unknown_99"


class TestScheduleTransformFunction:
    """Test the schedule transformation helper function."""

    def test_transform_schedule_entries_none(self) -> None:
        """Test transformation handles None input."""
        assert _transform_schedule_entries(None) is None

    def test_transform_schedule_entries_empty(self) -> None:
        """Test transformation handles empty list."""
        assert _transform_schedule_entries([]) == []

    def test_transform_all_control_modes(self) -> None:
        """Test all control modes are mapped correctly."""
        expected_modes = {
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
        assert expected_modes == SCHEDULE_CONTROL_MODES


class TestGetParamString:
    """Test _get_param_string helper function."""

    def test_param_string_direct_value(self) -> None:
        """Test extraction when value is a direct string."""
        params = [{"name": "ems_server", "value": "192.168.1.100"}]
        assert _get_param_string(params, "ems_server") == "192.168.1.100"

    def test_param_string_array_value(self) -> None:
        """Test extraction when value is in array format."""
        params = [{"name": "ems_server", "value": ["192.168.1.100"]}]
        assert _get_param_string(params, "ems_server") == "192.168.1.100"

    def test_param_string_empty_string(self) -> None:
        """Test extraction when value is empty string."""
        params = [{"name": "ems_server", "value": ""}]
        assert _get_param_string(params, "ems_server") == ""

    def test_param_string_not_found(self) -> None:
        """Test extraction when param not in list."""
        params = [{"name": "other_param", "value": "test"}]
        assert _get_param_string(params, "ems_server") is None

    def test_param_string_empty_list(self) -> None:
        """Test extraction with empty params list."""
        params = []
        assert _get_param_string(params, "ems_server") is None

    def test_param_string_not_list(self) -> None:
        """Test extraction when params is not a list."""
        params = {"name": "ems_server", "value": "test"}
        assert _get_param_string(params, "ems_server") is None

    def test_param_string_non_string_value(self) -> None:
        """Test extraction when value is not a string returns None."""
        params = [{"name": "ems_server", "value": 123}]
        assert _get_param_string(params, "ems_server") is None


class TestEmsModeValueFunctions:
    """Test EMS mode sensor value extraction functions."""

    def test_ems_mode_leader_when_multiple_units(self) -> None:
        """Test EMS mode returns 'leader' when ems list has more than one unit."""
        sensor = next(s for s in EMS_MODE_SENSORS if s.key == "ems_mode")
        data = {"ems": [{"ecu_id": "leader"}, {"ecu_id": "follower1"}]}
        result = sensor.value_fn(data)
        assert result == "leader"

    def test_ems_mode_leader_with_three_units(self) -> None:
        """Test EMS mode returns 'leader' with three or more units."""
        sensor = next(s for s in EMS_MODE_SENSORS if s.key == "ems_mode")
        data = {"ems": [{"ecu_id": "leader"}, {"ecu_id": "follower1"}, {"ecu_id": "follower2"}]}
        result = sensor.value_fn(data)
        assert result == "leader"

    def test_ems_mode_follower_when_single_unit(self) -> None:
        """Test EMS mode returns 'follower' when ems list has only one unit."""
        sensor = next(s for s in EMS_MODE_SENSORS if s.key == "ems_mode")
        data = {"ems": [{"ecu_id": "standalone"}]}
        result = sensor.value_fn(data)
        assert result == "follower"

    def test_ems_mode_follower_when_ems_list_empty(self) -> None:
        """Test EMS mode returns 'follower' when ems list is empty."""
        sensor = next(s for s in EMS_MODE_SENSORS if s.key == "ems_mode")
        data = {"ems": []}
        result = sensor.value_fn(data)
        assert result == "follower"

    def test_ems_mode_follower_when_empty_dict(self) -> None:
        """Test EMS mode returns 'follower' when data is empty dict."""
        sensor = next(s for s in EMS_MODE_SENSORS if s.key == "ems_mode")
        data = {}
        result = sensor.value_fn(data)
        assert result == "follower"

    def test_ems_mode_follower_when_not_dict(self) -> None:
        """Test EMS mode returns 'follower' when data is not a dict."""
        sensor = next(s for s in EMS_MODE_SENSORS if s.key == "ems_mode")
        data = []
        result = sensor.value_fn(data)
        assert result == "follower"

    def test_ems_mode_follower_when_ems_not_list(self) -> None:
        """Test EMS mode returns 'follower' when ems value is not a list."""
        sensor = next(s for s in EMS_MODE_SENSORS if s.key == "ems_mode")
        data = {"ems": "not_a_list"}
        result = sensor.value_fn(data)
        assert result == "follower"

    def test_ems_mode_is_diagnostic(self) -> None:
        """Test EMS mode is a diagnostic sensor enabled by default."""
        sensor = next(s for s in EMS_MODE_SENSORS if s.key == "ems_mode")
        assert sensor.entity_category == EntityCategory.DIAGNOSTIC
        assert sensor.entity_registry_enabled_default is True

    def test_ems_mode_uses_ems_data_key(self) -> None:
        """Test EMS mode sensor uses 'ems' as data_key."""
        sensor = next(s for s in EMS_MODE_SENSORS if s.key == "ems_mode")
        assert sensor.data_key == "ems"


class TestClusterOnlySensors:
    """Test cluster-only sensor value extraction functions."""

    def test_rated_power_extraction(self, mock_ems_data: dict) -> None:
        """Test rated power extraction from aggregated.ems_info.

        Note: _get_data() wraps aggregated into ems[0], so we simulate that here.
        """
        sensor = next(s for s in CLUSTER_ONLY_SENSORS if s.key == "rated_power")
        # Simulate what _get_data() does for CLUSTER sensors
        transformed_data = {"ems": [mock_ems_data["aggregated"]]}
        result = sensor.value_fn(transformed_data)
        assert result == 5000

    def test_rated_power_missing(self) -> None:
        """Test rated power returns None when aggregated data is missing."""
        sensor = next(s for s in CLUSTER_ONLY_SENSORS if s.key == "rated_power")
        data = {"ems": [{"ecu_id": "test"}]}
        result = sensor.value_fn(data)
        assert result is None

    def test_cluster_only_sensors_are_cluster_type(self) -> None:
        """Test all cluster-only sensors have CLUSTER device type."""
        for sensor in CLUSTER_ONLY_SENSORS:
            assert sensor.device_type == DeviceType.CLUSTER

    def test_cluster_only_sensors_have_translation_keys(self) -> None:
        """Test all cluster-only sensors have translation_key set."""
        for sensor in CLUSTER_ONLY_SENSORS:
            assert sensor.translation_key is not None
            assert sensor.translation_key == sensor.key


class TestSensorEntityAttributes:
    """Test sensor entity has correct attributes."""

    def test_all_sensors_have_translation_key(self) -> None:
        """Test all sensors have translation_key set."""
        for sensor in ALL_SENSORS:
            assert sensor.translation_key is not None
            assert sensor.translation_key == sensor.key


class TestDeviceTypeAssignment:
    """Test that sensors are assigned to the correct device type."""

    def test_cluster_sensors(self) -> None:
        """Test sensors assigned to cluster device."""
        cluster_sensor_keys = {
            "battery_soc",
            "inverter_power",
            "inverter_energy_produced",
            "inverter_energy_consumed",
            "ems_frequency",
            "available_capacity",
            "operation_state",
            "battery_state",
        }
        for sensor in ALL_SENSORS:
            if sensor.key in cluster_sensor_keys:
                assert sensor.device_type == DeviceType.CLUSTER, f"{sensor.key} should be CLUSTER"

    def test_ecu_sensors(self) -> None:
        """Test sensors assigned to ECU device."""
        ecu_sensor_keys = {
            "system_temperature",
            "mains_voltage",
            "mains_frequency",
            "uptime",
            "wifi_rssi",
            "ems_mode",
            "schedule_mode",
        }
        for sensor in ALL_SENSORS:
            if sensor.key in ecu_sensor_keys:
                assert sensor.device_type == DeviceType.ECU, f"{sensor.key} should be ECU"

    def test_all_sensors_have_device_type(self) -> None:
        """Test all sensors have a device_type assigned."""
        for sensor in ALL_SENSORS:
            assert hasattr(sensor, "device_type")
            assert sensor.device_type in (DeviceType.ECU, DeviceType.CLUSTER)


class TestClusterSensorDataSelection:
    """Test cluster sensors use aggregated data exclusively (no fallback to ems[0])."""

    def test_cluster_sensor_uses_aggregated_ems_data(self, mock_ems_data: dict) -> None:
        """Test cluster sensor returns value from aggregated.ems_data."""
        # aggregated.ems_data.soc_avg = 7550 (75.5%)
        # ems[0].ems_data.soc_avg = 7500 (75%)
        sensor = next(s for s in EMS_SENSORS if s.key == "battery_soc")
        # Simulate what _get_data does for cluster sensors
        aggregated = mock_ems_data.get("aggregated", {})
        data = {**mock_ems_data, "ems": [aggregated]}
        result = sensor.value_fn(data)
        assert result == 75.5  # From aggregated, not ems[0]

    def test_cluster_sensor_returns_none_when_aggregated_missing(self) -> None:
        """Test cluster sensor returns None when aggregated is missing entirely."""
        # Data without aggregated key - should NOT fall back to ems[0]
        data_without_aggregated = {
            "ems": [
                {
                    "ecu_id": "test123",
                    "ems_data": {"soc_avg": 7500, "power": 1500},
                }
            ]
        }
        sensor = next(s for s in EMS_SENSORS if s.key == "inverter_power")
        # Simulate what _get_data does: aggregated is empty dict when missing
        aggregated = data_without_aggregated.get("aggregated", {})
        data = {**data_without_aggregated, "ems": [aggregated]}
        result = sensor.value_fn(data)
        assert result is None  # No fallback to ems[0]

    def test_cluster_sensor_returns_none_when_aggregated_has_no_ems_data(self) -> None:
        """Test cluster sensor returns None when aggregated exists but has no ems_data."""
        # aggregated present but without ems_data
        data_without_ems_data = {
            "ems": [
                {
                    "ecu_id": "test123",
                    "ems_data": {"energy_produced": 10000000},  # Would be 10000 kWh
                }
            ],
            "aggregated": {
                "ems_info": {"capacity": 20000, "rated_power": 5000}
                # No ems_data here!
            },
        }
        sensor = next(s for s in EMS_SENSORS if s.key == "inverter_energy_produced")
        # Simulate what _get_data does
        aggregated = data_without_ems_data.get("aggregated", {})
        data = {**data_without_ems_data, "ems": [aggregated]}
        result = sensor.value_fn(data)
        assert result is None  # No fallback to ems[0]

    def test_cluster_energy_produced_from_aggregated(self, mock_ems_data: dict) -> None:
        """Test energy_produced comes from aggregated.ems_data, not ems[0]."""
        # aggregated.ems_data.energy_produced = 18000000 (18000 kWh)
        # ems[0].ems_data.energy_produced = 10000000 (10000 kWh)
        sensor = next(s for s in EMS_SENSORS if s.key == "inverter_energy_produced")
        aggregated = mock_ems_data.get("aggregated", {})
        data = {**mock_ems_data, "ems": [aggregated]}
        result = sensor.value_fn(data)
        assert result == 18000.0  # From aggregated, not ems[0]

    def test_cluster_energy_consumed_from_aggregated(self, mock_ems_data: dict) -> None:
        """Test energy_consumed comes from aggregated.ems_data, not ems[0]."""
        # aggregated.ems_data.energy_consumed = 16000000 (16000 kWh)
        # ems[0].ems_data.energy_consumed = 8000000 (8000 kWh)
        sensor = next(s for s in EMS_SENSORS if s.key == "inverter_energy_consumed")
        aggregated = mock_ems_data.get("aggregated", {})
        data = {**mock_ems_data, "ems": [aggregated]}
        result = sensor.value_fn(data)
        assert result == 16000.0  # From aggregated, not ems[0]

    def test_cluster_operation_state_from_aggregated(self, mock_ems_data: dict) -> None:
        """Test operation_state comes from aggregated.op_state_str."""
        sensor = next(s for s in EMS_SENSORS if s.key == "operation_state")
        aggregated = mock_ems_data.get("aggregated", {})
        data = {**mock_ems_data, "ems": [aggregated]}
        result = sensor.value_fn(data)
        assert result == "IDLE"  # From aggregated.op_state_str

    def test_cluster_battery_state_from_aggregated(self, mock_ems_data: dict) -> None:
        """Test battery_state comes from aggregated.ems_data.state_str."""
        sensor = next(s for s in EMS_SENSORS if s.key == "battery_state")
        aggregated = mock_ems_data.get("aggregated", {})
        data = {**mock_ems_data, "ems": [aggregated]}
        result = sensor.value_fn(data)
        assert result == "discharging"  # From aggregated.ems_data.state_str


class TestEcuRatedPowerSensor:
    """Test ECU-level rated_power sensor value extraction."""

    def test_ecu_rated_power_extraction(self, mock_ems_data: dict) -> None:
        """Test ECU rated_power extraction from ems[0].ems_info."""
        sensor = next(s for s in EMS_SENSORS if s.key == "rated_power")
        result = sensor.value_fn(mock_ems_data)
        assert result == 2500  # From ems[0].ems_info.rated_power

    def test_ecu_rated_power_missing_ems_info(self) -> None:
        """Test ECU rated_power returns None when ems_info is missing."""
        sensor = next(s for s in EMS_SENSORS if s.key == "rated_power")
        data = {"ems": [{"ecu_id": "test123", "ems_data": {}}]}
        result = sensor.value_fn(data)
        assert result is None

    def test_ecu_rated_power_missing_rated_power_field(self) -> None:
        """Test ECU rated_power returns None when rated_power field is missing."""
        sensor = next(s for s in EMS_SENSORS if s.key == "rated_power")
        data = {"ems": [{"ecu_id": "test123", "ems_info": {"capacity": 10000}}]}
        result = sensor.value_fn(data)
        assert result is None

    def test_ecu_rated_power_empty_ems_list(self) -> None:
        """Test ECU rated_power returns None when ems list is empty."""
        sensor = next(s for s in EMS_SENSORS if s.key == "rated_power")
        data = {"ems": []}
        result = sensor.value_fn(data)
        assert result is None

    def test_ecu_rated_power_is_diagnostic(self) -> None:
        """Test ECU rated_power is a diagnostic sensor."""
        sensor = next(s for s in EMS_SENSORS if s.key == "rated_power")
        assert sensor.entity_category == EntityCategory.DIAGNOSTIC

    def test_ecu_rated_power_is_ecu_device_type(self) -> None:
        """Test ECU rated_power has ECU device type."""
        sensor = next(s for s in EMS_SENSORS if s.key == "rated_power")
        assert sensor.device_type == DeviceType.ECU

    def test_ecu_rated_power_has_correct_units(self) -> None:
        """Test ECU rated_power has correct unit and device class."""
        sensor = next(s for s in EMS_SENSORS if s.key == "rated_power")
        assert sensor.native_unit_of_measurement == UnitOfPower.WATT
        assert sensor.device_class == SensorDeviceClass.POWER


class TestEmsPredictionSensors:
    """Test EMS prediction sensor value extraction functions."""

    def test_avail_charge_power_extraction(self, mock_ems_data: dict) -> None:
        """Test avail_charge_power extraction from ems_prediction."""
        sensor = next(s for s in EMS_SENSORS if s.key == "avail_charge_power")
        result = sensor.value_fn(mock_ems_data)
        assert result == 5000

    def test_avail_discharge_power_extraction(self, mock_ems_data: dict) -> None:
        """Test avail_discharge_power extraction from ems_prediction."""
        sensor = next(s for s in EMS_SENSORS if s.key == "avail_discharge_power")
        result = sensor.value_fn(mock_ems_data)
        assert result == 4500

    def test_avail_charge_energy_extraction(self, mock_ems_data: dict) -> None:
        """Test avail_charge_energy extraction from ems_prediction."""
        sensor = next(s for s in EMS_SENSORS if s.key == "avail_charge_energy")
        result = sensor.value_fn(mock_ems_data)
        assert result == 10000

    def test_avail_discharge_energy_extraction(self, mock_ems_data: dict) -> None:
        """Test avail_discharge_energy extraction from ems_prediction."""
        sensor = next(s for s in EMS_SENSORS if s.key == "avail_discharge_energy")
        result = sensor.value_fn(mock_ems_data)
        assert result == 8000

    def test_avail_inverter_charge_power_extraction(self, mock_ems_data: dict) -> None:
        """Test avail_inverter_charge_power extraction from ems_prediction."""
        sensor = next(s for s in EMS_SENSORS if s.key == "avail_inverter_charge_power")
        result = sensor.value_fn(mock_ems_data)
        assert result == 4800

    def test_avail_inverter_discharge_power_extraction(self, mock_ems_data: dict) -> None:
        """Test avail_inverter_discharge_power extraction from ems_prediction."""
        sensor = next(s for s in EMS_SENSORS if s.key == "avail_inverter_discharge_power")
        result = sensor.value_fn(mock_ems_data)
        assert result == 4300

    def test_avail_charge_power_missing(self) -> None:
        """Test avail_charge_power returns None when ems_prediction is missing."""
        sensor = next(s for s in EMS_SENSORS if s.key == "avail_charge_power")
        data = {"ems": [{"ecu_id": "test123", "ems_data": {}}]}
        result = sensor.value_fn(data)
        assert result is None

    def test_ems_prediction_sensors_are_cluster_type(self) -> None:
        """Test all EMS prediction sensors have CLUSTER device type."""
        prediction_sensor_keys = {
            "avail_charge_power",
            "avail_discharge_power",
            "avail_charge_energy",
            "avail_discharge_energy",
            "avail_inverter_charge_power",
            "avail_inverter_discharge_power",
        }
        for sensor in EMS_SENSORS:
            if sensor.key in prediction_sensor_keys:
                assert sensor.device_type == DeviceType.CLUSTER, f"{sensor.key} should be CLUSTER"

    def test_ems_prediction_sensors_have_measurement_state_class(self) -> None:
        """Test all EMS prediction sensors have MEASUREMENT state class."""
        prediction_sensor_keys = {
            "avail_charge_power",
            "avail_discharge_power",
            "avail_charge_energy",
            "avail_discharge_energy",
            "avail_inverter_charge_power",
            "avail_inverter_discharge_power",
        }
        for sensor in EMS_SENSORS:
            if sensor.key in prediction_sensor_keys:
                assert (
                    sensor.state_class == SensorStateClass.MEASUREMENT
                ), f"{sensor.key} should have MEASUREMENT state class"

    def test_ems_prediction_power_sensors_have_correct_units(self) -> None:
        """Test EMS prediction power sensors have correct unit and device class."""
        power_sensor_keys = {
            "avail_charge_power",
            "avail_discharge_power",
            "avail_inverter_charge_power",
            "avail_inverter_discharge_power",
        }
        for sensor in EMS_SENSORS:
            if sensor.key in power_sensor_keys:
                assert (
                    sensor.native_unit_of_measurement == UnitOfPower.WATT
                ), f"{sensor.key} should have WATT unit"
                assert (
                    sensor.device_class == SensorDeviceClass.POWER
                ), f"{sensor.key} should have POWER device class"

    def test_ems_prediction_energy_sensors_have_correct_units(self) -> None:
        """Test EMS prediction energy sensors have correct unit and device class."""
        from homeassistant.const import UnitOfEnergy

        energy_sensor_keys = {
            "avail_charge_energy",
            "avail_discharge_energy",
        }
        for sensor in EMS_SENSORS:
            if sensor.key in energy_sensor_keys:
                assert (
                    sensor.native_unit_of_measurement == UnitOfEnergy.WATT_HOUR
                ), f"{sensor.key} should have WATT_HOUR unit"
                assert (
                    sensor.device_class == SensorDeviceClass.ENERGY_STORAGE
                ), f"{sensor.key} should have ENERGY_STORAGE device class"

    def test_cluster_avail_charge_power_from_aggregated(self, mock_ems_data: dict) -> None:
        """Test avail_charge_power comes from aggregated.ems_prediction, not ems[0]."""
        # aggregated.ems_prediction.avail_ch_pwr = 10000
        # ems[0].ems_prediction.avail_ch_pwr = 5000
        sensor = next(s for s in EMS_SENSORS if s.key == "avail_charge_power")
        aggregated = mock_ems_data.get("aggregated", {})
        data = {**mock_ems_data, "ems": [aggregated]}
        result = sensor.value_fn(data)
        assert result == 10000  # From aggregated, not ems[0]

    def test_cluster_avail_discharge_energy_from_aggregated(self, mock_ems_data: dict) -> None:
        """Test avail_discharge_energy comes from aggregated.ems_prediction, not ems[0]."""
        # aggregated.ems_prediction.avail_di_energy = 16000
        # ems[0].ems_prediction.avail_di_energy = 8000
        sensor = next(s for s in EMS_SENSORS if s.key == "avail_discharge_energy")
        aggregated = mock_ems_data.get("aggregated", {})
        data = {**mock_ems_data, "ems": [aggregated]}
        result = sensor.value_fn(data)
        assert result == 16000  # From aggregated, not ems[0]


class TestGetSensorByType:
    """Test _get_sensor_by_type helper function."""

    def test_get_grid_sensor(self) -> None:
        """Test extracting grid sensor from sensors array."""
        data = {
            "sensors": [
                {"type": "grid", "total_power": 1500, "rssi": -45},
                {"type": "solar", "total_power": 2000, "rssi": -50},
            ]
        }
        result = _get_sensor_by_type(data, "grid")
        assert result == {"type": "grid", "total_power": 1500, "rssi": -45}

    def test_get_solar_sensor(self) -> None:
        """Test extracting solar sensor from sensors array."""
        data = {
            "sensors": [
                {"type": "grid", "total_power": 1500},
                {"type": "solar", "total_power": 2000},
            ]
        }
        result = _get_sensor_by_type(data, "solar")
        assert result == {"type": "solar", "total_power": 2000}

    def test_get_load_sensor(self) -> None:
        """Test extracting load sensor from sensors array."""
        data = {
            "sensors": [
                {"type": "grid", "total_power": 1500},
                {"type": "load", "total_power": 800},
            ]
        }
        result = _get_sensor_by_type(data, "load")
        assert result == {"type": "load", "total_power": 800}

    def test_sensor_type_not_found(self) -> None:
        """Test returns empty dict when sensor type not in array."""
        data = {
            "sensors": [
                {"type": "grid", "total_power": 1500},
            ]
        }
        result = _get_sensor_by_type(data, "solar")
        assert result == {}

    def test_empty_sensors_array(self) -> None:
        """Test returns empty dict when sensors array is empty."""
        data = {"sensors": []}
        result = _get_sensor_by_type(data, "grid")
        assert result == {}

    def test_missing_sensors_key(self) -> None:
        """Test returns empty dict when sensors key is missing."""
        data = {"ems": []}
        result = _get_sensor_by_type(data, "grid")
        assert result == {}

    def test_missing_data(self) -> None:
        """Test returns empty dict when data is empty."""
        data: dict = {}
        result = _get_sensor_by_type(data, "grid")
        assert result == {}

    def test_sensors_not_list(self) -> None:
        """Test returns empty dict when sensors is not a list."""
        data = {"sensors": "not_a_list"}
        result = _get_sensor_by_type(data, "grid")
        assert result == {}

    def test_sensor_item_not_dict(self) -> None:
        """Test skips non-dict items in sensors array."""
        data = {"sensors": ["not_a_dict", {"type": "grid", "total_power": 1500}]}
        result = _get_sensor_by_type(data, "grid")
        assert result == {"type": "grid", "total_power": 1500}


class TestExternalSensorSensors:
    """Test external sensor (grid, solar, load) value extraction functions."""

    @pytest.fixture
    def mock_ems_with_sensors(self) -> dict:
        """Return mock EMS data with sensors array at top level."""
        return {
            "sensors": [
                {
                    "type": "grid",
                    "total_power": 1500,
                    "energy_imported": 100.5,
                    "energy_exported": 50.25,
                    "rssi": -45,
                    "pdr": 95,
                    "available": True,
                },
                {
                    "type": "solar",
                    "total_power": 2000,
                    "energy_imported": 500.75,
                    "energy_exported": 0.0,
                    "rssi": -50,
                    "pdr": 98,
                    "available": True,
                },
                {
                    "type": "load",
                    "total_power": 800,
                    "energy_imported": 200.0,
                    "energy_exported": 10.0,
                    "rssi": -55,
                    "pdr": 90,
                    "available": True,
                },
            ]
        }

    def test_grid_power_extraction(self, mock_ems_with_sensors: dict) -> None:
        """Test grid power extraction."""
        sensor = next(s for s in EXTERNAL_SENSOR_SENSORS if s.key == "grid_power")
        result = sensor.value_fn(mock_ems_with_sensors)
        assert result == 1500

    def test_grid_energy_imported_extraction(self, mock_ems_with_sensors: dict) -> None:
        """Test grid energy imported extraction."""
        sensor = next(s for s in EXTERNAL_SENSOR_SENSORS if s.key == "grid_energy_imported")
        result = sensor.value_fn(mock_ems_with_sensors)
        assert result == 100.5

    def test_grid_energy_exported_extraction(self, mock_ems_with_sensors: dict) -> None:
        """Test grid energy exported extraction."""
        sensor = next(s for s in EXTERNAL_SENSOR_SENSORS if s.key == "grid_energy_exported")
        result = sensor.value_fn(mock_ems_with_sensors)
        assert result == 50.25

    def test_grid_rssi_extraction(self, mock_ems_with_sensors: dict) -> None:
        """Test grid rssi extraction."""
        sensor = next(s for s in EXTERNAL_SENSOR_SENSORS if s.key == "grid_rssi")
        result = sensor.value_fn(mock_ems_with_sensors)
        assert result == -45

    def test_solar_power_extraction(self, mock_ems_with_sensors: dict) -> None:
        """Test solar power extraction."""
        sensor = next(s for s in EXTERNAL_SENSOR_SENSORS if s.key == "solar_power")
        result = sensor.value_fn(mock_ems_with_sensors)
        assert result == 2000

    def test_solar_energy_imported_extraction(self, mock_ems_with_sensors: dict) -> None:
        """Test solar energy imported extraction."""
        sensor = next(s for s in EXTERNAL_SENSOR_SENSORS if s.key == "solar_energy_imported")
        result = sensor.value_fn(mock_ems_with_sensors)
        assert result == 500.75

    def test_solar_energy_exported_extraction(self, mock_ems_with_sensors: dict) -> None:
        """Test solar energy exported extraction."""
        sensor = next(s for s in EXTERNAL_SENSOR_SENSORS if s.key == "solar_energy_exported")
        result = sensor.value_fn(mock_ems_with_sensors)
        assert result == 0.0

    def test_solar_rssi_extraction(self, mock_ems_with_sensors: dict) -> None:
        """Test solar rssi extraction."""
        sensor = next(s for s in EXTERNAL_SENSOR_SENSORS if s.key == "solar_rssi")
        result = sensor.value_fn(mock_ems_with_sensors)
        assert result == -50

    def test_load_power_extraction(self, mock_ems_with_sensors: dict) -> None:
        """Test load power extraction."""
        sensor = next(s for s in EXTERNAL_SENSOR_SENSORS if s.key == "load_power")
        result = sensor.value_fn(mock_ems_with_sensors)
        assert result == 800

    def test_load_energy_imported_extraction(self, mock_ems_with_sensors: dict) -> None:
        """Test load energy imported extraction."""
        sensor = next(s for s in EXTERNAL_SENSOR_SENSORS if s.key == "load_energy_imported")
        result = sensor.value_fn(mock_ems_with_sensors)
        assert result == 200.0

    def test_load_energy_exported_extraction(self, mock_ems_with_sensors: dict) -> None:
        """Test load energy exported extraction."""
        sensor = next(s for s in EXTERNAL_SENSOR_SENSORS if s.key == "load_energy_exported")
        result = sensor.value_fn(mock_ems_with_sensors)
        assert result == 10.0

    def test_load_rssi_extraction(self, mock_ems_with_sensors: dict) -> None:
        """Test load rssi extraction."""
        sensor = next(s for s in EXTERNAL_SENSOR_SENSORS if s.key == "load_rssi")
        result = sensor.value_fn(mock_ems_with_sensors)
        assert result == -55

    def test_grid_power_missing_sensor(self) -> None:
        """Test grid power returns None when grid sensor not present."""
        sensor = next(s for s in EXTERNAL_SENSOR_SENSORS if s.key == "grid_power")
        data = {"sensors": [{"function_name": "solar", "total_power": 2000}]}
        result = sensor.value_fn(data)
        assert result is None

    def test_solar_power_missing_sensor(self) -> None:
        """Test solar power returns None when solar sensor not present."""
        sensor = next(s for s in EXTERNAL_SENSOR_SENSORS if s.key == "solar_power")
        data = {"sensors": [{"function_name": "grid", "total_power": 1500}]}
        result = sensor.value_fn(data)
        assert result is None

    def test_load_power_missing_sensor(self) -> None:
        """Test load power returns None when load sensor not present."""
        sensor = next(s for s in EXTERNAL_SENSOR_SENSORS if s.key == "load_power")
        data = {"sensors": [{"function_name": "grid", "total_power": 1500}]}
        result = sensor.value_fn(data)
        assert result is None

    def test_external_sensor_sensors_are_ecu_type(self) -> None:
        """Test all external sensor sensors have ECU device type."""
        for sensor in EXTERNAL_SENSOR_SENSORS:
            assert sensor.device_type == DeviceType.ECU, f"{sensor.key} should be ECU"

    def test_external_sensor_sensors_have_translation_keys(self) -> None:
        """Test all external sensor sensors have translation_key set."""
        for sensor in EXTERNAL_SENSOR_SENSORS:
            assert sensor.translation_key is not None
            assert sensor.translation_key == sensor.key

    def test_power_sensors_have_correct_units(self) -> None:
        """Test power sensors have correct unit and device class."""
        power_sensor_keys = {"grid_power", "solar_power", "load_power"}
        for sensor in EXTERNAL_SENSOR_SENSORS:
            if sensor.key in power_sensor_keys:
                assert (
                    sensor.native_unit_of_measurement == UnitOfPower.WATT
                ), f"{sensor.key} should have WATT unit"
                assert (
                    sensor.device_class == SensorDeviceClass.POWER
                ), f"{sensor.key} should have POWER device class"
                assert (
                    sensor.state_class == SensorStateClass.MEASUREMENT
                ), f"{sensor.key} should have MEASUREMENT state class"

    def test_energy_sensors_have_correct_units(self) -> None:
        """Test energy sensors have correct unit and device class."""
        from homeassistant.const import UnitOfEnergy

        energy_sensor_keys = {
            "grid_energy_imported",
            "grid_energy_exported",
            "solar_energy_imported",
            "solar_energy_exported",
            "load_energy_imported",
            "load_energy_exported",
        }
        for sensor in EXTERNAL_SENSOR_SENSORS:
            if sensor.key in energy_sensor_keys:
                assert (
                    sensor.native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
                ), f"{sensor.key} should have KILO_WATT_HOUR unit"
                assert (
                    sensor.device_class == SensorDeviceClass.ENERGY
                ), f"{sensor.key} should have ENERGY device class"
                assert (
                    sensor.state_class == SensorStateClass.TOTAL_INCREASING
                ), f"{sensor.key} should have TOTAL_INCREASING state class"

    def test_rssi_sensors_have_correct_units(self) -> None:
        """Test RSSI sensors have correct unit and device class."""
        from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT

        rssi_sensor_keys = {"grid_rssi", "solar_rssi", "load_rssi"}
        for sensor in EXTERNAL_SENSOR_SENSORS:
            if sensor.key in rssi_sensor_keys:
                assert (
                    sensor.native_unit_of_measurement == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
                ), f"{sensor.key} should have dBm unit"
                assert (
                    sensor.device_class == SensorDeviceClass.SIGNAL_STRENGTH
                ), f"{sensor.key} should have SIGNAL_STRENGTH device class"
                assert (
                    sensor.entity_category == EntityCategory.DIAGNOSTIC
                ), f"{sensor.key} should be DIAGNOSTIC category"
                # grid_rssi and solar_rssi are enabled by default, load_rssi is disabled
                if sensor.key == "load_rssi":
                    assert (
                        sensor.entity_registry_enabled_default is False
                    ), f"{sensor.key} should be disabled by default"
                else:
                    # grid_rssi and solar_rssi don't have entity_registry_enabled_default set (defaults to True)
                    assert (
                        sensor.entity_registry_enabled_default is not False
                    ), f"{sensor.key} should be enabled by default"

    def test_all_sensors_includes_external_sensors(self) -> None:
        """Test ALL_SENSORS includes EXTERNAL_SENSOR_SENSORS."""
        expected = (
            len(EMS_SENSORS)
            + len(MAINS_SENSORS)
            + len(STATUS_SENSORS)
            + len(SCHEDULE_SENSORS)
            + len(EMS_MODE_SENSORS)
            + len(OTA_SENSORS)
            + len(EXTERNAL_SENSOR_SENSORS)
        )
        assert len(ALL_SENSORS) == expected
