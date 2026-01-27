"""Tests for Homevolt Local select platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import EntityCategory

from custom_components.homevolt_local.select import (
    PARALLEL_UPDATES,
    SELECTS,
    HomevoltSelect,
    _get_param_string,
)


class TestGetParamString:
    """Test _get_param_string helper function."""

    def test_param_string_direct_value(self) -> None:
        """Test extraction when value is a direct string."""
        params = [{"name": "ledstrip_mode", "value": "soc"}]
        assert _get_param_string(params, "ledstrip_mode") == "soc"

    def test_param_string_array_value(self) -> None:
        """Test extraction when value is in array format."""
        params = [{"name": "ledstrip_mode", "value": ["on"]}]
        assert _get_param_string(params, "ledstrip_mode") == "on"

    def test_param_string_not_found(self) -> None:
        """Test extraction when param not in list."""
        params = [{"name": "other_param", "value": "test"}]
        assert _get_param_string(params, "ledstrip_mode") is None

    def test_param_string_empty_list(self) -> None:
        """Test extraction with empty params list."""
        params = []
        assert _get_param_string(params, "ledstrip_mode") is None

    def test_param_string_not_list(self) -> None:
        """Test extraction when params is not a list."""
        params = {"name": "ledstrip_mode", "value": "soc"}
        assert _get_param_string(params, "ledstrip_mode") is None


class TestSelectDescriptions:
    """Test select entity descriptions."""

    def test_parallel_updates_constant(self) -> None:
        """Test PARALLEL_UPDATES is set to 1."""
        assert PARALLEL_UPDATES == 1

    def test_ledstrip_mode_select_description(self) -> None:
        """Test ledstrip_mode select description."""
        select = next(s for s in SELECTS if s.key == "ledstrip_mode")
        assert select.translation_key == "ledstrip_mode"
        assert select.param_key == "ledstrip_mode"
        assert select.options == ["unset", "off", "on", "soc", "dem", "ser"]
        assert select.entity_category == EntityCategory.CONFIG

    def test_all_selects_have_translation_key(self) -> None:
        """Test all selects have translation_key set."""
        for select in SELECTS:
            assert select.translation_key is not None
            assert select.translation_key == select.key


class TestHomevoltSelect:
    """Test HomevoltSelect entity."""

    def test_select_current_option(self) -> None:
        """Test select current_option returns correct value."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": [{"name": "ledstrip_mode", "value": "soc"}]}

        description = SELECTS[0]
        select = HomevoltSelect(coordinator, description)

        assert select.current_option == "soc"

    def test_select_current_option_unset_when_empty(self) -> None:
        """Test select current_option returns 'unset' for empty string."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": [{"name": "ledstrip_mode", "value": ""}]}

        description = SELECTS[0]
        select = HomevoltSelect(coordinator, description)

        assert select.current_option == "unset"

    def test_select_current_option_unset_when_missing(self) -> None:
        """Test select current_option returns 'unset' when param not found."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}

        description = SELECTS[0]
        select = HomevoltSelect(coordinator, description)

        assert select.current_option == "unset"

    def test_select_current_option_none_when_invalid(self) -> None:
        """Test select current_option returns None for invalid option."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": [{"name": "ledstrip_mode", "value": "invalid"}]}

        description = SELECTS[0]
        select = HomevoltSelect(coordinator, description)

        assert select.current_option is None

    def test_select_unique_id(self) -> None:
        """Test select unique_id is correctly set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}

        description = SELECTS[0]
        select = HomevoltSelect(coordinator, description)

        assert select.unique_id == "test123_ledstrip_mode"

    def test_select_has_entity_name(self) -> None:
        """Test select has _attr_has_entity_name set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}

        description = SELECTS[0]
        select = HomevoltSelect(coordinator, description)

        assert select._attr_has_entity_name is True

    @pytest.mark.asyncio
    async def test_async_select_option(self) -> None:
        """Test async_select_option calls API and refreshes coordinator."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}
        coordinator.api = MagicMock()
        coordinator.api.set_param = AsyncMock()
        coordinator.async_request_refresh = AsyncMock()

        description = SELECTS[0]
        select = HomevoltSelect(coordinator, description)

        await select.async_select_option("on")

        coordinator.api.set_param.assert_called_once_with("ledstrip_mode", "on")
        coordinator.async_request_refresh.assert_called_once()

    def test_select_device_info(self) -> None:
        """Test select device_info is correctly set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {"params": []}

        description = SELECTS[0]
        select = HomevoltSelect(coordinator, description)

        device_info = select.device_info
        assert device_info is not None
        assert ("homevolt_local", "test123") in device_info["identifiers"]
        assert device_info["name"] == "Test Homevolt"
        assert device_info["manufacturer"] == "Tibber"
        assert device_info["model"] == "Homevolt Battery"
        assert device_info["sw_version"] == "1.0.0"
