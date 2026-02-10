"""Tests for Homevolt Local button platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.button import ButtonDeviceClass
from homeassistant.const import EntityCategory

from custom_components.homevolt_local.button import (
    PARALLEL_UPDATES,
    HomevoltClearScheduleButton,
    HomevoltRebootButton,
    HomevoltSetChargeButton,
    HomevoltSetDischargeButton,
    HomevoltSetIdleButton,
)


class TestButtonConstants:
    """Test button platform constants."""

    def test_parallel_updates_constant(self) -> None:
        """Test PARALLEL_UPDATES is set to 1."""
        assert PARALLEL_UPDATES == 1


class TestHomevoltClearScheduleButton:
    """Test HomevoltClearScheduleButton entity."""

    def test_button_has_entity_name(self) -> None:
        """Test button has _attr_has_entity_name set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltClearScheduleButton(coordinator)

        assert button._attr_has_entity_name is True

    def test_button_translation_key(self) -> None:
        """Test button has correct translation_key."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltClearScheduleButton(coordinator)

        assert button._attr_translation_key == "clear_schedule"

    def test_button_entity_category(self) -> None:
        """Test button has CONFIG entity category."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltClearScheduleButton(coordinator)

        assert button._attr_entity_category == EntityCategory.CONFIG

    def test_button_unique_id(self) -> None:
        """Test button unique_id is correctly set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltClearScheduleButton(coordinator)

        assert button.unique_id == "test123_clear_schedule"

    def test_button_device_info(self) -> None:
        """Test button device_info is correctly set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltClearScheduleButton(coordinator)

        device_info = button.device_info
        assert device_info is not None
        assert ("homevolt_local", "test123") in device_info["identifiers"]
        assert device_info["name"] == "Test Homevolt"
        assert device_info["manufacturer"] == "Tibber"
        assert device_info["model"] == "Homevolt Battery"
        assert device_info["sw_version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_async_press_calls_api(self) -> None:
        """Test async_press calls the API clear_schedule method."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}
        coordinator.api = MagicMock()
        coordinator.api.clear_schedule = AsyncMock(
            return_value={"command": "sched_clear", "output": "OK", "exit_code": 0}
        )
        coordinator.async_request_refresh = AsyncMock()

        button = HomevoltClearScheduleButton(coordinator)

        await button.async_press()

        coordinator.api.clear_schedule.assert_called_once()
        coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_press_refreshes_coordinator(self) -> None:
        """Test async_press refreshes coordinator after API call."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}
        coordinator.api = MagicMock()
        coordinator.api.clear_schedule = AsyncMock(
            return_value={"command": "sched_clear", "output": "OK", "exit_code": 0}
        )
        coordinator.async_request_refresh = AsyncMock()

        button = HomevoltClearScheduleButton(coordinator)

        await button.async_press()

        # Verify refresh is called after the API call
        coordinator.async_request_refresh.assert_called_once()

    def test_button_unique_id_different_device(self) -> None:
        """Test button unique_id with different device ID."""
        coordinator = MagicMock()
        coordinator.device_id = "abc456"
        coordinator.device_name = "Another Homevolt"
        coordinator.firmware_version = "2.0.0"
        coordinator.data = {}

        button = HomevoltClearScheduleButton(coordinator)

        assert button.unique_id == "abc456_clear_schedule"


class TestHomevoltSetIdleButton:
    """Test HomevoltSetIdleButton entity."""

    def test_button_has_entity_name(self) -> None:
        """Test button has _attr_has_entity_name set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltSetIdleButton(coordinator)

        assert button._attr_has_entity_name is True

    def test_button_translation_key(self) -> None:
        """Test button has correct translation_key."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltSetIdleButton(coordinator)

        assert button._attr_translation_key == "set_idle"

    def test_button_entity_category(self) -> None:
        """Test button has CONFIG entity category."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltSetIdleButton(coordinator)

        assert button._attr_entity_category == EntityCategory.CONFIG

    def test_button_unique_id(self) -> None:
        """Test button unique_id is correctly set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltSetIdleButton(coordinator)

        assert button.unique_id == "test123_set_idle"

    def test_button_device_info(self) -> None:
        """Test button device_info is correctly set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltSetIdleButton(coordinator)

        device_info = button.device_info
        assert device_info is not None
        assert ("homevolt_local", "test123") in device_info["identifiers"]
        assert device_info["name"] == "Test Homevolt"
        assert device_info["manufacturer"] == "Tibber"
        assert device_info["model"] == "Homevolt Battery"
        assert device_info["sw_version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_async_press_calls_api(self) -> None:
        """Test async_press calls the API set_idle method."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}
        coordinator.api = MagicMock()
        coordinator.api.set_idle = AsyncMock(
            return_value={"command": "sched_set 0", "output": "OK", "exit_code": 0}
        )
        coordinator.async_request_refresh = AsyncMock()

        button = HomevoltSetIdleButton(coordinator)

        await button.async_press()

        coordinator.api.set_idle.assert_called_once()
        coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_press_refreshes_coordinator(self) -> None:
        """Test async_press refreshes coordinator after API call."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}
        coordinator.api = MagicMock()
        coordinator.api.set_idle = AsyncMock(
            return_value={"command": "sched_set 0", "output": "OK", "exit_code": 0}
        )
        coordinator.async_request_refresh = AsyncMock()

        button = HomevoltSetIdleButton(coordinator)

        await button.async_press()

        # Verify refresh is called after the API call
        coordinator.async_request_refresh.assert_called_once()

    def test_button_unique_id_different_device(self) -> None:
        """Test button unique_id with different device ID."""
        coordinator = MagicMock()
        coordinator.device_id = "abc456"
        coordinator.device_name = "Another Homevolt"
        coordinator.firmware_version = "2.0.0"
        coordinator.data = {}

        button = HomevoltSetIdleButton(coordinator)

        assert button.unique_id == "abc456_set_idle"


class TestHomevoltSetChargeButton:
    """Test HomevoltSetChargeButton entity."""

    def test_button_has_entity_name(self) -> None:
        """Test button has _attr_has_entity_name set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltSetChargeButton(coordinator)

        assert button._attr_has_entity_name is True

    def test_button_translation_key(self) -> None:
        """Test button has correct translation_key."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltSetChargeButton(coordinator)

        assert button._attr_translation_key == "set_charge"

    def test_button_entity_category(self) -> None:
        """Test button has CONFIG entity category."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltSetChargeButton(coordinator)

        assert button._attr_entity_category == EntityCategory.CONFIG

    def test_button_unique_id(self) -> None:
        """Test button unique_id is correctly set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltSetChargeButton(coordinator)

        assert button.unique_id == "test123_set_charge"

    @pytest.mark.asyncio
    async def test_async_press_calls_api(self) -> None:
        """Test async_press calls the API set_charge method."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}
        coordinator.api = MagicMock()
        coordinator.api.set_charge = AsyncMock(
            return_value={"command": "sched_set 1", "output": "OK", "exit_code": 0}
        )
        coordinator.async_request_refresh = AsyncMock()

        button = HomevoltSetChargeButton(coordinator)

        await button.async_press()

        coordinator.api.set_charge.assert_called_once()
        coordinator.async_request_refresh.assert_called_once()


class TestHomevoltSetDischargeButton:
    """Test HomevoltSetDischargeButton entity."""

    def test_button_has_entity_name(self) -> None:
        """Test button has _attr_has_entity_name set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltSetDischargeButton(coordinator)

        assert button._attr_has_entity_name is True

    def test_button_translation_key(self) -> None:
        """Test button has correct translation_key."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltSetDischargeButton(coordinator)

        assert button._attr_translation_key == "set_discharge"

    def test_button_entity_category(self) -> None:
        """Test button has CONFIG entity category."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltSetDischargeButton(coordinator)

        assert button._attr_entity_category == EntityCategory.CONFIG

    def test_button_unique_id(self) -> None:
        """Test button unique_id is correctly set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltSetDischargeButton(coordinator)

        assert button.unique_id == "test123_set_discharge"

    @pytest.mark.asyncio
    async def test_async_press_calls_api(self) -> None:
        """Test async_press calls the API set_discharge method."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}
        coordinator.api = MagicMock()
        coordinator.api.set_discharge = AsyncMock(
            return_value={"command": "sched_set 2", "output": "OK", "exit_code": 0}
        )
        coordinator.async_request_refresh = AsyncMock()

        button = HomevoltSetDischargeButton(coordinator)

        await button.async_press()

        coordinator.api.set_discharge.assert_called_once()
        coordinator.async_request_refresh.assert_called_once()


class TestHomevoltRebootButton:
    """Test HomevoltRebootButton entity."""

    def test_button_has_entity_name(self) -> None:
        """Test button has _attr_has_entity_name set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltRebootButton(coordinator)

        assert button._attr_has_entity_name is True

    def test_button_translation_key(self) -> None:
        """Test button has correct translation_key."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltRebootButton(coordinator)

        assert button._attr_translation_key == "reboot"

    def test_button_entity_category(self) -> None:
        """Test button has DIAGNOSTIC entity category."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltRebootButton(coordinator)

        assert button._attr_entity_category == EntityCategory.DIAGNOSTIC

    def test_button_device_class(self) -> None:
        """Test button has RESTART device class."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltRebootButton(coordinator)

        assert button._attr_device_class == ButtonDeviceClass.RESTART

    def test_button_unique_id(self) -> None:
        """Test button unique_id is correctly set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltRebootButton(coordinator)

        assert button.unique_id == "test123_reboot"

    def test_button_device_info(self) -> None:
        """Test button device_info is correctly set."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}

        button = HomevoltRebootButton(coordinator)

        device_info = button.device_info
        assert device_info is not None
        assert ("homevolt_local", "test123") in device_info["identifiers"]
        assert device_info["name"] == "Test Homevolt"
        assert device_info["manufacturer"] == "Tibber"
        assert device_info["model"] == "Homevolt Battery"
        assert device_info["sw_version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_async_press_calls_api(self) -> None:
        """Test async_press calls the API reboot method."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}
        coordinator.api = MagicMock()
        coordinator.api.reboot = AsyncMock(
            return_value={"command": "reset_hard", "output": "OK", "exit_code": 0}
        )

        button = HomevoltRebootButton(coordinator)

        await button.async_press()

        coordinator.api.reboot.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_press_does_not_refresh_coordinator(self) -> None:
        """Test async_press does not refresh coordinator (device will be offline)."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "Test Homevolt"
        coordinator.firmware_version = "1.0.0"
        coordinator.data = {}
        coordinator.api = MagicMock()
        coordinator.api.reboot = AsyncMock(
            return_value={"command": "reset_hard", "output": "OK", "exit_code": 0}
        )
        coordinator.async_request_refresh = AsyncMock()

        button = HomevoltRebootButton(coordinator)

        await button.async_press()

        coordinator.async_request_refresh.assert_not_called()

    def test_button_unique_id_different_device(self) -> None:
        """Test button unique_id with different device ID."""
        coordinator = MagicMock()
        coordinator.device_id = "abc456"
        coordinator.device_name = "Another Homevolt"
        coordinator.firmware_version = "2.0.0"
        coordinator.data = {}

        button = HomevoltRebootButton(coordinator)

        assert button.unique_id == "abc456_reboot"
