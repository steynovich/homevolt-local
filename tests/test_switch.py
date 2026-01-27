"""Tests for Homevolt Local switch platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import EntityCategory

from custom_components.homevolt_local.switch import (
    PARALLEL_UPDATES,
    SWITCHES,
    HomevoltSwitch,
    _get_param_bool,
)


class TestGetParamBool:
    """Test _get_param_bool helper function."""

    def test_param_bool_true_bool(self) -> None:
        """Test extraction when value is True boolean."""
        params = [{"name": "settings_local", "value": True}]
        assert _get_param_bool(params, "settings_local") is True

    def test_param_bool_false_bool(self) -> None:
        """Test extraction when value is False boolean."""
        params = [{"name": "settings_local", "value": False}]
        assert _get_param_bool(params, "settings_local") is False

    def test_param_bool_true_string(self) -> None:
        """Test extraction when value is 'true' string."""
        params = [{"name": "settings_local", "value": "true"}]
        assert _get_param_bool(params, "settings_local") is True

    def test_param_bool_false_string(self) -> None:
        """Test extraction when value is 'false' string."""
        params = [{"name": "settings_local", "value": "false"}]
        assert _get_param_bool(params, "settings_local") is False

    def test_param_bool_one_int(self) -> None:
        """Test extraction when value is 1 integer."""
        params = [{"name": "settings_local", "value": 1}]
        assert _get_param_bool(params, "settings_local") is True

    def test_param_bool_zero_int(self) -> None:
        """Test extraction when value is 0 integer."""
        params = [{"name": "settings_local", "value": 0}]
        assert _get_param_bool(params, "settings_local") is False

    def test_param_bool_one_string(self) -> None:
        """Test extraction when value is '1' string."""
        params = [{"name": "settings_local", "value": "1"}]
        assert _get_param_bool(params, "settings_local") is True

    def test_param_bool_zero_string(self) -> None:
        """Test extraction when value is '0' string."""
        params = [{"name": "settings_local", "value": "0"}]
        assert _get_param_bool(params, "settings_local") is False

    def test_param_bool_not_found(self) -> None:
        """Test extraction when param not in list."""
        params = [{"name": "other_param", "value": "some_value"}]
        assert _get_param_bool(params, "settings_local") is None

    def test_param_bool_empty_list(self) -> None:
        """Test extraction with empty params list."""
        params = []
        assert _get_param_bool(params, "settings_local") is None

    def test_param_bool_among_other_params(self) -> None:
        """Test extraction when param is among other params."""
        params = [
            {"name": "ecu_mdns_instance_name", "value": "My Homevolt"},
            {"name": "settings_local", "value": True},
            {"name": "other_param", "value": "some_value"},
        ]
        assert _get_param_bool(params, "settings_local") is True

    def test_param_bool_true_array(self) -> None:
        """Test extraction when value is [True] array (actual API format)."""
        params = [{"name": "settings_local", "value": [True]}]
        assert _get_param_bool(params, "settings_local") is True

    def test_param_bool_false_array(self) -> None:
        """Test extraction when value is [False] array (actual API format)."""
        params = [{"name": "settings_local", "value": [False]}]
        assert _get_param_bool(params, "settings_local") is False

    def test_param_bool_different_param(self) -> None:
        """Test extraction with different param name."""
        params = [{"name": "ota_enable_esp32", "value": True}]
        assert _get_param_bool(params, "ota_enable_esp32") is True


class TestSwitchDescriptions:
    """Test switch entity descriptions."""

    def test_parallel_updates_constant(self) -> None:
        """Test PARALLEL_UPDATES is set to 1."""
        assert PARALLEL_UPDATES == 1

    def test_settings_local_switch_description(self) -> None:
        """Test settings_local switch description."""
        switch = next(s for s in SWITCHES if s.key == "settings_local")
        assert switch.translation_key == "settings_local"
        assert switch.param_key == "settings_local"

    def test_ota_enable_switch_description(self) -> None:
        """Test ota_enable switch description."""
        switch = next(s for s in SWITCHES if s.key == "ota_enable")
        assert switch.translation_key == "ota_enable"
        assert switch.param_key == "ota_enable"
        assert switch.entity_category == EntityCategory.DIAGNOSTIC

    def test_ota_enable_esp32_switch_description(self) -> None:
        """Test ota_enable_esp32 switch description."""
        switch = next(s for s in SWITCHES if s.key == "ota_enable_esp32")
        assert switch.translation_key == "ota_enable_esp32"
        assert switch.param_key == "ota_enable_esp32"
        assert switch.entity_category == EntityCategory.DIAGNOSTIC

    def test_ota_enable_hub_web_switch_description(self) -> None:
        """Test ota_enable_hub_web switch description."""
        switch = next(s for s in SWITCHES if s.key == "ota_enable_hub_web")
        assert switch.translation_key == "ota_enable_hub_web"
        assert switch.param_key == "ota_enable_hub_web"
        assert switch.entity_category == EntityCategory.DIAGNOSTIC

    def test_ota_enable_bg95_m3_switch_description(self) -> None:
        """Test ota_enable_bg95_m3 switch description."""
        switch = next(s for s in SWITCHES if s.key == "ota_enable_bg95_m3")
        assert switch.translation_key == "ota_enable_bg95_m3"
        assert switch.param_key == "ota_enable_bg95_m3"
        assert switch.entity_category == EntityCategory.DIAGNOSTIC

    def test_all_switches_have_translation_key(self) -> None:
        """Test all switches have translation_key set."""
        for switch in SWITCHES:
            assert switch.translation_key is not None
            assert switch.translation_key == switch.key


class TestHomevoltSwitch:
    """Test HomevoltSwitch entity."""

    def test_switch_is_on_true(self) -> None:
        """Test switch is_on returns True when settings_local is true."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": [{"name": "settings_local", "value": True}]}

        description = SWITCHES[0]
        switch = HomevoltSwitch(coordinator, description)

        assert switch.is_on is True

    def test_switch_is_on_false(self) -> None:
        """Test switch is_on returns False when settings_local is false."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": [{"name": "settings_local", "value": False}]}

        description = SWITCHES[0]
        switch = HomevoltSwitch(coordinator, description)

        assert switch.is_on is False

    def test_switch_is_on_none_when_missing(self) -> None:
        """Test switch is_on returns None when param not found."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}

        description = SWITCHES[0]
        switch = HomevoltSwitch(coordinator, description)

        assert switch.is_on is None

    def test_switch_is_on_none_when_params_not_list(self) -> None:
        """Test switch is_on returns None when params is not a list."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": {}}

        description = SWITCHES[0]
        switch = HomevoltSwitch(coordinator, description)

        assert switch.is_on is None

    def test_switch_unique_id(self) -> None:
        """Test switch unique_id is correctly set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}

        description = SWITCHES[0]
        switch = HomevoltSwitch(coordinator, description)

        assert switch.unique_id == "test123_settings_local"

    def test_switch_has_entity_name(self) -> None:
        """Test switch has _attr_has_entity_name set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}

        description = SWITCHES[0]
        switch = HomevoltSwitch(coordinator, description)

        assert switch._attr_has_entity_name is True

    @pytest.mark.asyncio
    async def test_async_turn_on(self) -> None:
        """Test async_turn_on calls API and refreshes coordinator."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}
        coordinator.api = MagicMock()
        coordinator.api.set_param = AsyncMock()
        coordinator.async_request_refresh = AsyncMock()

        description = SWITCHES[0]
        switch = HomevoltSwitch(coordinator, description)

        await switch.async_turn_on()

        coordinator.api.set_param.assert_called_once_with("settings_local", "true")
        coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_turn_off(self) -> None:
        """Test async_turn_off calls API and refreshes coordinator."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}
        coordinator.api = MagicMock()
        coordinator.api.set_param = AsyncMock()
        coordinator.async_request_refresh = AsyncMock()

        description = SWITCHES[0]
        switch = HomevoltSwitch(coordinator, description)

        await switch.async_turn_off()

        coordinator.api.set_param.assert_called_once_with("settings_local", "false")
        coordinator.async_request_refresh.assert_called_once()

    def test_switch_device_info(self) -> None:
        """Test switch device_info is correctly set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}

        description = SWITCHES[0]
        switch = HomevoltSwitch(coordinator, description)

        device_info = switch.device_info
        assert device_info is not None
        assert ("homevolt_local", "test123") in device_info["identifiers"]
        assert device_info["name"] == "Test Homevolt"
        assert device_info["manufacturer"] == "Tibber"
        assert device_info["model"] == "Homevolt Battery"
        assert device_info["sw_version"] == "1.0.0"
