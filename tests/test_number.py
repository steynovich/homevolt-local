"""Tests for Homevolt Local number platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import EntityCategory

from custom_components.homevolt_local.number import (
    NUMBERS,
    PARALLEL_UPDATES,
    HomevoltNumber,
    _get_param_value,
)


class TestGetParamValue:
    """Test _get_param_value helper function."""

    def test_param_value_int(self) -> None:
        """Test extraction when value is an integer."""
        params = [{"name": "ecu_main_fuse_size_a", "value": 25}]
        assert _get_param_value(params, "ecu_main_fuse_size_a") == 25

    def test_param_value_float(self) -> None:
        """Test extraction when value is a float."""
        params = [{"name": "ecu_main_fuse_size_a", "value": 25.5}]
        assert _get_param_value(params, "ecu_main_fuse_size_a") == 25

    def test_param_value_array_int(self) -> None:
        """Test extraction when value is [int] array (actual API format)."""
        params = [{"name": "ecu_main_fuse_size_a", "value": [25]}]
        assert _get_param_value(params, "ecu_main_fuse_size_a") == 25

    def test_param_value_array_float(self) -> None:
        """Test extraction when value is [float] array."""
        params = [{"name": "ecu_main_fuse_size_a", "value": [25.7]}]
        assert _get_param_value(params, "ecu_main_fuse_size_a") == 25

    def test_param_not_found(self) -> None:
        """Test extraction when param not in list."""
        params = [{"name": "other_param", "value": 10}]
        assert _get_param_value(params, "ecu_main_fuse_size_a") is None

    def test_param_empty_list(self) -> None:
        """Test extraction with empty params list."""
        params = []
        assert _get_param_value(params, "ecu_main_fuse_size_a") is None

    def test_param_among_other_params(self) -> None:
        """Test extraction when param is among other params."""
        params = [
            {"name": "ecu_mdns_instance_name", "value": "My Homevolt"},
            {"name": "ecu_main_fuse_size_a", "value": [25]},
            {"name": "other_param", "value": "some_value"},
        ]
        assert _get_param_value(params, "ecu_main_fuse_size_a") == 25

    def test_param_value_string_returns_none(self) -> None:
        """Test extraction when value is a string returns None."""
        params = [{"name": "ecu_main_fuse_size_a", "value": "25"}]
        assert _get_param_value(params, "ecu_main_fuse_size_a") is None

    def test_param_value_empty_array_returns_none(self) -> None:
        """Test extraction when value is empty array returns None."""
        params = [{"name": "ecu_main_fuse_size_a", "value": []}]
        assert _get_param_value(params, "ecu_main_fuse_size_a") is None

    def test_group_fuse_size(self) -> None:
        """Test extraction of group fuse size."""
        params = [{"name": "ecu_group_fuse_size_a", "value": [16]}]
        assert _get_param_value(params, "ecu_group_fuse_size_a") == 16


class TestNumberDescriptions:
    """Test number entity descriptions."""

    def test_parallel_updates_constant(self) -> None:
        """Test PARALLEL_UPDATES is set to 1."""
        assert PARALLEL_UPDATES == 1

    def test_main_fuse_size_description(self) -> None:
        """Test ecu_main_fuse_size_a number description."""
        number = next(n for n in NUMBERS if n.key == "ecu_main_fuse_size_a")
        assert number.translation_key == "ecu_main_fuse_size_a"
        assert number.param_key == "ecu_main_fuse_size_a"
        assert number.native_unit_of_measurement == "A"
        assert number.native_min_value == 0
        assert number.native_max_value == 100
        assert number.native_step == 1
        assert number.entity_category == EntityCategory.CONFIG

    def test_group_fuse_size_description(self) -> None:
        """Test ecu_group_fuse_size_a number description."""
        number = next(n for n in NUMBERS if n.key == "ecu_group_fuse_size_a")
        assert number.translation_key == "ecu_group_fuse_size_a"
        assert number.param_key == "ecu_group_fuse_size_a"
        assert number.native_unit_of_measurement == "A"
        assert number.native_min_value == 0
        assert number.native_max_value == 100
        assert number.native_step == 1
        assert number.entity_category == EntityCategory.CONFIG

    def test_ledstrip_bright_max_description(self) -> None:
        """Test ledstrip_bright_max number description."""
        number = next(n for n in NUMBERS if n.key == "ledstrip_bright_max")
        assert number.translation_key == "ledstrip_bright_max"
        assert number.param_key == "ledstrip_bright_max"
        assert number.native_unit_of_measurement == "%"
        assert number.native_min_value == 0
        assert number.native_max_value == 100
        assert number.native_step == 1
        assert number.entity_category == EntityCategory.CONFIG

    def test_ledstrip_bright_min_description(self) -> None:
        """Test ledstrip_bright_min number description."""
        number = next(n for n in NUMBERS if n.key == "ledstrip_bright_min")
        assert number.translation_key == "ledstrip_bright_min"
        assert number.param_key == "ledstrip_bright_min"
        assert number.native_unit_of_measurement == "%"
        assert number.native_min_value == 0
        assert number.native_max_value == 100
        assert number.native_step == 1
        assert number.entity_category == EntityCategory.CONFIG

    def test_ledstrip_mode_on_hue_description(self) -> None:
        """Test ledstrip_mode_on_hue number description."""
        number = next(n for n in NUMBERS if n.key == "ledstrip_mode_on_hue")
        assert number.translation_key == "ledstrip_mode_on_hue"
        assert number.param_key == "ledstrip_mode_on_hue"
        assert number.native_unit_of_measurement == "°"
        assert number.native_min_value == 0
        assert number.native_max_value == 360
        assert number.native_step == 1
        assert number.entity_category == EntityCategory.CONFIG

    def test_ledstrip_mode_on_saturation_description(self) -> None:
        """Test ledstrip_mode_on_saturation number description."""
        number = next(n for n in NUMBERS if n.key == "ledstrip_mode_on_saturation")
        assert number.translation_key == "ledstrip_mode_on_saturation"
        assert number.param_key == "ledstrip_mode_on_saturation"
        assert number.native_unit_of_measurement == "%"
        assert number.native_min_value == 0
        assert number.native_max_value == 100
        assert number.native_step == 1
        assert number.entity_category == EntityCategory.CONFIG

    def test_all_numbers_have_translation_key(self) -> None:
        """Test all numbers have translation_key set."""
        for number in NUMBERS:
            assert number.translation_key is not None
            assert number.translation_key == number.key


class TestHomevoltNumber:
    """Test HomevoltNumber entity."""

    def test_number_native_value(self) -> None:
        """Test number native_value returns correct value."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": [{"name": "ecu_main_fuse_size_a", "value": [25]}]}

        description = next(n for n in NUMBERS if n.key == "ecu_main_fuse_size_a")
        number = HomevoltNumber(coordinator, description)

        assert number.native_value == 25

    def test_number_native_value_none_when_missing(self) -> None:
        """Test number native_value returns None when param not found."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}

        description = next(n for n in NUMBERS if n.key == "ecu_main_fuse_size_a")
        number = HomevoltNumber(coordinator, description)

        assert number.native_value is None

    def test_number_native_value_none_when_params_not_list(self) -> None:
        """Test number native_value returns None when params is not a list."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": {}}

        description = next(n for n in NUMBERS if n.key == "ecu_main_fuse_size_a")
        number = HomevoltNumber(coordinator, description)

        assert number.native_value is None

    def test_number_unique_id(self) -> None:
        """Test number unique_id is correctly set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}

        description = next(n for n in NUMBERS if n.key == "ecu_main_fuse_size_a")
        number = HomevoltNumber(coordinator, description)

        assert number.unique_id == "test123_ecu_main_fuse_size_a"

    def test_number_has_entity_name(self) -> None:
        """Test number has _attr_has_entity_name set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}

        description = next(n for n in NUMBERS if n.key == "ecu_main_fuse_size_a")
        number = HomevoltNumber(coordinator, description)

        assert number._attr_has_entity_name is True

    @pytest.mark.asyncio
    async def test_async_set_native_value(self) -> None:
        """Test async_set_native_value calls API and refreshes coordinator."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}
        coordinator.api = MagicMock()
        coordinator.api.set_param = AsyncMock()
        coordinator.async_request_refresh = AsyncMock()

        description = next(n for n in NUMBERS if n.key == "ecu_main_fuse_size_a")
        number = HomevoltNumber(coordinator, description)

        await number.async_set_native_value(30)

        coordinator.api.set_param.assert_called_once_with("ecu_main_fuse_size_a", "30")
        coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_native_value_converts_float_to_int(self) -> None:
        """Test async_set_native_value converts float to int string."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}
        coordinator.api = MagicMock()
        coordinator.api.set_param = AsyncMock()
        coordinator.async_request_refresh = AsyncMock()

        description = next(n for n in NUMBERS if n.key == "ecu_main_fuse_size_a")
        number = HomevoltNumber(coordinator, description)

        await number.async_set_native_value(30.7)

        coordinator.api.set_param.assert_called_once_with("ecu_main_fuse_size_a", "30")
        coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_native_value_group_fuse(self) -> None:
        """Test async_set_native_value for group fuse size."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}
        coordinator.api = MagicMock()
        coordinator.api.set_param = AsyncMock()
        coordinator.async_request_refresh = AsyncMock()

        description = next(n for n in NUMBERS if n.key == "ecu_group_fuse_size_a")
        number = HomevoltNumber(coordinator, description)

        await number.async_set_native_value(16)

        coordinator.api.set_param.assert_called_once_with("ecu_group_fuse_size_a", "16")
        coordinator.async_request_refresh.assert_called_once()

    def test_number_device_info(self) -> None:
        """Test number device_info is correctly set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}

        description = next(n for n in NUMBERS if n.key == "ecu_main_fuse_size_a")
        number = HomevoltNumber(coordinator, description)

        device_info = number.device_info
        assert device_info is not None
        assert ("homevolt_local", "test123") in device_info["identifiers"]
        assert device_info["name"] == "Test Homevolt"
        assert device_info["manufacturer"] == "Tibber"
        assert device_info["model"] == "Homevolt Battery"
        assert device_info["sw_version"] == "1.0.0"
