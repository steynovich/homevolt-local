"""Tests for Homevolt Local binary sensor platform."""

from unittest.mock import MagicMock

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import EntityCategory

from custom_components.homevolt_local.binary_sensor import (
    BINARY_SENSORS,
    PARALLEL_UPDATES,
    HomevoltBinarySensor,
    LTEConnectedBinarySensor,
    WiFiConnectedBinarySensor,
    _get_param_bool,
)


class TestGetParamBool:
    """Test _get_param_bool helper function."""

    def test_param_bool_true_bool(self) -> None:
        """Test extraction when value is True boolean."""
        params = [{"name": "mqtt_valid", "value": True}]
        assert _get_param_bool(params, "mqtt_valid") is True

    def test_param_bool_false_bool(self) -> None:
        """Test extraction when value is False boolean."""
        params = [{"name": "mqtt_valid", "value": False}]
        assert _get_param_bool(params, "mqtt_valid") is False

    def test_param_bool_true_array(self) -> None:
        """Test extraction when value is [True] array."""
        params = [{"name": "mqtt_valid", "value": [True]}]
        assert _get_param_bool(params, "mqtt_valid") is True

    def test_param_bool_false_array(self) -> None:
        """Test extraction when value is [False] array."""
        params = [{"name": "mqtt_valid", "value": [False]}]
        assert _get_param_bool(params, "mqtt_valid") is False

    def test_param_bool_not_found(self) -> None:
        """Test extraction when param not in list."""
        params = [{"name": "other_param", "value": True}]
        assert _get_param_bool(params, "mqtt_valid") is None

    def test_param_bool_empty_list(self) -> None:
        """Test extraction with empty params list."""
        params = []
        assert _get_param_bool(params, "mqtt_valid") is None

    def test_param_bool_not_list(self) -> None:
        """Test extraction when params is not a list."""
        params = {"name": "mqtt_valid", "value": True}
        assert _get_param_bool(params, "mqtt_valid") is None


class TestBinarySensorDescriptions:
    """Test binary sensor entity descriptions."""

    def test_parallel_updates_constant(self) -> None:
        """Test PARALLEL_UPDATES is set to 1."""
        assert PARALLEL_UPDATES == 1

    def test_mqtt_valid_binary_sensor_description(self) -> None:
        """Test mqtt_valid binary sensor description."""
        sensor = next(s for s in BINARY_SENSORS if s.key == "mqtt_valid")
        assert sensor.translation_key == "mqtt_valid"
        assert sensor.param_key == "mqtt_valid"
        assert sensor.device_class == BinarySensorDeviceClass.CONNECTIVITY
        assert sensor.entity_category == EntityCategory.DIAGNOSTIC

    def test_all_binary_sensors_have_translation_key(self) -> None:
        """Test all binary sensors have translation_key set."""
        for sensor in BINARY_SENSORS:
            assert sensor.translation_key is not None
            assert sensor.translation_key == sensor.key


class TestHomevoltBinarySensor:
    """Test HomevoltBinarySensor entity."""

    def test_binary_sensor_is_on_true(self) -> None:
        """Test binary sensor is_on returns True."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": [{"name": "mqtt_valid", "value": True}]}

        description = BINARY_SENSORS[0]
        sensor = HomevoltBinarySensor(coordinator, description)

        assert sensor.is_on is True

    def test_binary_sensor_is_on_false(self) -> None:
        """Test binary sensor is_on returns False."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": [{"name": "mqtt_valid", "value": False}]}

        description = BINARY_SENSORS[0]
        sensor = HomevoltBinarySensor(coordinator, description)

        assert sensor.is_on is False

    def test_binary_sensor_is_on_none_when_missing(self) -> None:
        """Test binary sensor is_on returns None when param not found."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}

        description = BINARY_SENSORS[0]
        sensor = HomevoltBinarySensor(coordinator, description)

        assert sensor.is_on is None

    def test_binary_sensor_unique_id(self) -> None:
        """Test binary sensor unique_id is correctly set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}

        description = BINARY_SENSORS[0]
        sensor = HomevoltBinarySensor(coordinator, description)

        assert sensor.unique_id == "test123_mqtt_valid"

    def test_binary_sensor_has_entity_name(self) -> None:
        """Test binary sensor has _attr_has_entity_name set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}

        description = BINARY_SENSORS[0]
        sensor = HomevoltBinarySensor(coordinator, description)

        assert sensor._attr_has_entity_name is True

    def test_binary_sensor_device_info(self) -> None:
        """Test binary sensor device_info is correctly set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}

        description = BINARY_SENSORS[0]
        sensor = HomevoltBinarySensor(coordinator, description)

        device_info = sensor.device_info
        assert device_info is not None
        assert ("homevolt_local", "test123") in device_info["identifiers"]
        assert device_info["name"] == "Test Homevolt"
        assert device_info["manufacturer"] == "Tibber"
        assert device_info["model"] == "Homevolt Battery"
        assert device_info["sw_version"] == "1.0.0"


class TestWiFiConnectedBinarySensor:
    """Test WiFiConnectedBinarySensor entity."""

    def test_wifi_connected_is_on_true(self) -> None:
        """Test WiFi connected sensor is_on returns True."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"status": {"wifi_status": {"connected": True, "ssid": "MyNetwork"}}}

        sensor = WiFiConnectedBinarySensor(coordinator)

        assert sensor.is_on is True

    def test_wifi_connected_is_on_false(self) -> None:
        """Test WiFi connected sensor is_on returns False."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"status": {"wifi_status": {"connected": False}}}

        sensor = WiFiConnectedBinarySensor(coordinator)

        assert sensor.is_on is False

    def test_wifi_connected_is_on_none_when_missing(self) -> None:
        """Test WiFi connected sensor is_on returns None when data missing."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"status": {}}

        sensor = WiFiConnectedBinarySensor(coordinator)

        assert sensor.is_on is None

    def test_wifi_connected_ssid_attribute(self) -> None:
        """Test WiFi connected sensor includes ssid attribute."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"status": {"wifi_status": {"connected": True, "ssid": "MyNetwork"}}}

        sensor = WiFiConnectedBinarySensor(coordinator)

        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["ssid"] == "MyNetwork"

    def test_wifi_connected_no_ssid_attribute_when_missing(self) -> None:
        """Test WiFi connected sensor returns None when ssid missing."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"status": {"wifi_status": {"connected": True}}}

        sensor = WiFiConnectedBinarySensor(coordinator)

        assert sensor.extra_state_attributes is None

    def test_wifi_connected_unique_id(self) -> None:
        """Test WiFi connected sensor unique_id is correctly set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"status": {}}

        sensor = WiFiConnectedBinarySensor(coordinator)

        assert sensor.unique_id == "test123_wifi_connected"


class TestLTEConnectedBinarySensor:
    """Test LTEConnectedBinarySensor entity."""

    def test_lte_connected_is_on_true(self) -> None:
        """Test LTE connected sensor is_on returns True when operator_name is set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"status": {"lte_status": {"operator_name": "Telenor"}}}

        sensor = LTEConnectedBinarySensor(coordinator)

        assert sensor.is_on is True

    def test_lte_connected_is_on_false(self) -> None:
        """Test LTE connected sensor is_on returns False when operator_name is empty."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"status": {"lte_status": {"operator_name": ""}}}

        sensor = LTEConnectedBinarySensor(coordinator)

        assert sensor.is_on is False

    def test_lte_connected_is_on_none_when_missing(self) -> None:
        """Test LTE connected sensor is_on returns None when data missing."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"status": {}}

        sensor = LTEConnectedBinarySensor(coordinator)

        assert sensor.is_on is None

    def test_lte_connected_operator_attribute(self) -> None:
        """Test LTE connected sensor includes operator attribute."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"status": {"lte_status": {"operator_name": "Telenor"}}}

        sensor = LTEConnectedBinarySensor(coordinator)

        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["operator"] == "Telenor"

    def test_lte_connected_no_operator_attribute_when_empty(self) -> None:
        """Test LTE connected sensor returns None when operator_name is empty."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"status": {"lte_status": {"operator_name": ""}}}

        sensor = LTEConnectedBinarySensor(coordinator)

        assert sensor.extra_state_attributes is None

    def test_lte_connected_unique_id(self) -> None:
        """Test LTE connected sensor unique_id is correctly set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"status": {}}

        sensor = LTEConnectedBinarySensor(coordinator)

        assert sensor.unique_id == "test123_lte_connected"
