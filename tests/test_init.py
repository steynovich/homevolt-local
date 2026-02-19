"""Tests for Homevolt Local integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components.homevolt_local import (
    SCHEDULE_ENTRY_SCHEMA,
    SERVICE_CLEAR_SCHEDULE,
    SERVICE_REBOOT,
    SERVICE_SET_CHARGE,
    SERVICE_SET_DISCHARGE,
    SERVICE_SET_FULL_SOLAR_EXPORT,
    SERVICE_SET_GRID_CHARGE,
    SERVICE_SET_GRID_CHARGE_DISCHARGE,
    SERVICE_SET_GRID_DISCHARGE,
    SERVICE_SET_IDLE,
    SERVICE_SET_SCHEDULE,
    SERVICE_SET_SCHEDULE_SCHEMA,
    SERVICE_SET_SOLAR_CHARGE,
    SERVICE_SET_SOLAR_CHARGE_DISCHARGE,
    async_unload_entry,
    validate_iso8601_datetime,
)
from custom_components.homevolt_local.api import (
    HomevoltAuthError,
    HomevoltConnectionError,
    HomevoltRateLimitError,
)
from custom_components.homevolt_local.const import DOMAIN


class TestValidateIso8601Datetime:
    """Tests for ISO 8601 datetime validation."""

    def test_valid_datetime(self) -> None:
        """Test valid ISO 8601 datetime string."""
        assert validate_iso8601_datetime("2024-01-15T23:00:00") == "2024-01-15T23:00:00"
        assert validate_iso8601_datetime("2024-12-31T00:00:00") == "2024-12-31T00:00:00"
        assert validate_iso8601_datetime("2025-06-15T12:30:45") == "2025-06-15T12:30:45"

    def test_invalid_format_space(self) -> None:
        """Test datetime with space instead of T is rejected."""
        with pytest.raises(vol.Invalid) as exc_info:
            validate_iso8601_datetime("2024-01-15 23:00:00")
        assert "Invalid datetime format" in str(exc_info.value)

    def test_invalid_format_missing_seconds(self) -> None:
        """Test datetime without seconds is rejected."""
        with pytest.raises(vol.Invalid):
            validate_iso8601_datetime("2024-01-15T23:00")

    def test_invalid_format_extra_chars(self) -> None:
        """Test datetime with extra characters is rejected."""
        with pytest.raises(vol.Invalid):
            validate_iso8601_datetime("2024-01-15T23:00:00Z")

    def test_command_injection_attempt(self) -> None:
        """Test command injection attempt is rejected."""
        with pytest.raises(vol.Invalid):
            validate_iso8601_datetime("2024-01-15T23:00:00; rm -rf /")

    def test_command_injection_pipe(self) -> None:
        """Test pipe injection attempt is rejected."""
        with pytest.raises(vol.Invalid):
            validate_iso8601_datetime("2024-01-15T23:00:00 | cat /etc/passwd")

    def test_command_injection_backtick(self) -> None:
        """Test backtick injection attempt is rejected."""
        with pytest.raises(vol.Invalid):
            validate_iso8601_datetime("2024-01-15T23:00:00`whoami`")

    def test_non_string_input(self) -> None:
        """Test non-string input is rejected."""
        with pytest.raises(vol.Invalid) as exc_info:
            validate_iso8601_datetime(12345)  # type: ignore[arg-type]
        assert "Expected string" in str(exc_info.value)


class TestScheduleEntrySchema:
    """Tests for SCHEDULE_ENTRY_SCHEMA validation."""

    def test_valid_entry_minimal(self) -> None:
        """Test valid entry with only required field."""
        result = SCHEDULE_ENTRY_SCHEMA({"type": 1})
        assert result["type"] == 1

    def test_valid_entry_all_fields(self) -> None:
        """Test valid entry with all fields at boundary values."""
        entry = {
            "type": 9,
            "from_time": "2024-01-15T00:00:00",
            "to_time": "2024-01-15T23:59:59",
            "min_soc": 0,
            "max_soc": 100,
            "setpoint": -25000,
            "max_charge": 25000,
            "max_discharge": 25000,
            "import_limit": -25000,
            "export_limit": 25000,
        }
        result = SCHEDULE_ENTRY_SCHEMA(entry)
        assert result["setpoint"] == -25000
        assert result["max_charge"] == 25000

    def test_setpoint_rejects_below_min(self) -> None:
        """Test setpoint rejects values below -25000."""
        with pytest.raises(vol.Invalid):
            SCHEDULE_ENTRY_SCHEMA({"type": 1, "setpoint": -25001})

    def test_setpoint_rejects_above_max(self) -> None:
        """Test setpoint rejects values above 25000."""
        with pytest.raises(vol.Invalid):
            SCHEDULE_ENTRY_SCHEMA({"type": 1, "setpoint": 25001})

    def test_max_charge_rejects_negative(self) -> None:
        """Test max_charge rejects negative values."""
        with pytest.raises(vol.Invalid):
            SCHEDULE_ENTRY_SCHEMA({"type": 1, "max_charge": -1})

    def test_max_charge_rejects_above_max(self) -> None:
        """Test max_charge rejects values above 25000."""
        with pytest.raises(vol.Invalid):
            SCHEDULE_ENTRY_SCHEMA({"type": 1, "max_charge": 25001})

    def test_max_discharge_rejects_negative(self) -> None:
        """Test max_discharge rejects negative values."""
        with pytest.raises(vol.Invalid):
            SCHEDULE_ENTRY_SCHEMA({"type": 1, "max_discharge": -1})

    def test_max_discharge_rejects_above_max(self) -> None:
        """Test max_discharge rejects values above 25000."""
        with pytest.raises(vol.Invalid):
            SCHEDULE_ENTRY_SCHEMA({"type": 1, "max_discharge": 25001})

    def test_import_limit_rejects_below_min(self) -> None:
        """Test import_limit rejects values below -25000."""
        with pytest.raises(vol.Invalid):
            SCHEDULE_ENTRY_SCHEMA({"type": 1, "import_limit": -25001})

    def test_import_limit_rejects_above_max(self) -> None:
        """Test import_limit rejects values above 25000."""
        with pytest.raises(vol.Invalid):
            SCHEDULE_ENTRY_SCHEMA({"type": 1, "import_limit": 25001})

    def test_export_limit_rejects_below_min(self) -> None:
        """Test export_limit rejects values below -25000."""
        with pytest.raises(vol.Invalid):
            SCHEDULE_ENTRY_SCHEMA({"type": 1, "export_limit": -25001})

    def test_export_limit_rejects_above_max(self) -> None:
        """Test export_limit rejects values above 25000."""
        with pytest.raises(vol.Invalid):
            SCHEDULE_ENTRY_SCHEMA({"type": 1, "export_limit": 25001})


class TestServiceSetScheduleSchema:
    """Tests for SERVICE_SET_SCHEDULE_SCHEMA validation."""

    def test_valid_single_entry(self) -> None:
        """Test valid schema with single entry."""
        result = SERVICE_SET_SCHEDULE_SCHEMA(
            {
                "device_id": "test_device",
                "schedule": [{"type": 1}],
            }
        )
        assert result["device_id"] == "test_device"
        assert len(result["schedule"]) == 1

    def test_rejects_empty_schedule(self) -> None:
        """Test schema rejects empty schedule list."""
        with pytest.raises(vol.Invalid):
            SERVICE_SET_SCHEDULE_SCHEMA(
                {
                    "device_id": "test_device",
                    "schedule": [],
                }
            )

    def test_rejects_schedule_over_100_entries(self) -> None:
        """Test schema rejects schedule with more than 100 entries."""
        entries = [{"type": 1} for _ in range(101)]
        with pytest.raises(vol.Invalid):
            SERVICE_SET_SCHEDULE_SCHEMA(
                {
                    "device_id": "test_device",
                    "schedule": entries,
                }
            )

    def test_accepts_schedule_with_100_entries(self) -> None:
        """Test schema accepts schedule with exactly 100 entries."""
        entries = [{"type": 1} for _ in range(100)]
        result = SERVICE_SET_SCHEDULE_SCHEMA(
            {
                "device_id": "test_device",
                "schedule": entries,
            }
        )
        assert len(result["schedule"]) == 100


async def test_setup_entry_auth_error(
    hass: HomeAssistant,
    mock_config_data: dict,
) -> None:
    """Test setup fails with auth error."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.homevolt_local import async_setup_entry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        unique_id="test123",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.homevolt_local.HomevoltApi",
        autospec=True,
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.test_connection = AsyncMock(side_effect=HomevoltAuthError("Invalid credentials"))

        with pytest.raises(ConfigEntryAuthFailed):
            await async_setup_entry(hass, entry)


async def test_setup_entry_rate_limit_error(
    hass: HomeAssistant,
    mock_config_data: dict,
) -> None:
    """Test setup fails with rate limit error."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.homevolt_local import async_setup_entry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        unique_id="test123",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.homevolt_local.HomevoltApi",
        autospec=True,
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.test_connection = AsyncMock(side_effect=HomevoltRateLimitError("Rate limited"))

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_data: dict,
) -> None:
    """Test setup fails with connection error."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.homevolt_local import async_setup_entry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        unique_id="test123",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.homevolt_local.HomevoltApi",
        autospec=True,
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.test_connection = AsyncMock(
            side_effect=HomevoltConnectionError("Connection failed")
        )

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)


class TestAsyncUnloadEntry:
    """Tests for async_unload_entry service cleanup."""

    @pytest.mark.asyncio
    async def test_services_removed_when_last_entry_unloaded(
        self, hass: HomeAssistant
    ) -> None:
        """Test services are removed when the last config entry is unloaded."""
        # Register some services so we can check they get removed
        all_services = [
            SERVICE_CLEAR_SCHEDULE,
            SERVICE_SET_IDLE,
            SERVICE_SET_CHARGE,
            SERVICE_SET_DISCHARGE,
            SERVICE_SET_GRID_CHARGE,
            SERVICE_SET_GRID_DISCHARGE,
            SERVICE_SET_GRID_CHARGE_DISCHARGE,
            SERVICE_SET_SOLAR_CHARGE,
            SERVICE_SET_SOLAR_CHARGE_DISCHARGE,
            SERVICE_SET_FULL_SOLAR_EXPORT,
            SERVICE_SET_SCHEDULE,
            SERVICE_REBOOT,
        ]
        for svc in all_services:
            hass.services.async_register(DOMAIN, svc, AsyncMock())

        # Verify services are registered
        for svc in all_services:
            assert hass.services.has_service(DOMAIN, svc)

        # Create a mock entry with no other entries remaining
        entry = MagicMock()
        entry.entry_id = "entry1"

        # async_entries returns only this entry (so after removal, none remain)
        hass.config_entries.async_entries = MagicMock(return_value=[entry])

        with patch.object(
            hass.config_entries, "async_unload_platforms", return_value=True
        ):
            result = await async_unload_entry(hass, entry)

        assert result is True
        # All services should be removed
        for svc in all_services:
            assert not hass.services.has_service(DOMAIN, svc)

    @pytest.mark.asyncio
    async def test_services_kept_when_other_entries_remain(
        self, hass: HomeAssistant
    ) -> None:
        """Test services are kept when other config entries still exist."""
        all_services = [
            SERVICE_CLEAR_SCHEDULE,
            SERVICE_SET_IDLE,
            SERVICE_SET_CHARGE,
            SERVICE_SET_DISCHARGE,
            SERVICE_SET_GRID_CHARGE,
            SERVICE_SET_GRID_DISCHARGE,
            SERVICE_SET_GRID_CHARGE_DISCHARGE,
            SERVICE_SET_SOLAR_CHARGE,
            SERVICE_SET_SOLAR_CHARGE_DISCHARGE,
            SERVICE_SET_FULL_SOLAR_EXPORT,
            SERVICE_SET_SCHEDULE,
            SERVICE_REBOOT,
        ]
        for svc in all_services:
            hass.services.async_register(DOMAIN, svc, AsyncMock())

        entry1 = MagicMock()
        entry1.entry_id = "entry1"
        entry2 = MagicMock()
        entry2.entry_id = "entry2"

        # Two entries exist - unloading entry1 leaves entry2
        hass.config_entries.async_entries = MagicMock(return_value=[entry1, entry2])

        with patch.object(
            hass.config_entries, "async_unload_platforms", return_value=True
        ):
            result = await async_unload_entry(hass, entry1)

        assert result is True
        # Services should still be registered
        for svc in all_services:
            assert hass.services.has_service(DOMAIN, svc)

    @pytest.mark.asyncio
    async def test_services_not_removed_when_unload_fails(
        self, hass: HomeAssistant
    ) -> None:
        """Test services are not removed when platform unload fails."""
        all_services = [
            SERVICE_CLEAR_SCHEDULE,
            SERVICE_SET_IDLE,
        ]
        for svc in all_services:
            hass.services.async_register(DOMAIN, svc, AsyncMock())

        entry = MagicMock()
        entry.entry_id = "entry1"
        hass.config_entries.async_entries = MagicMock(return_value=[entry])

        with patch.object(
            hass.config_entries, "async_unload_platforms", return_value=False
        ):
            result = await async_unload_entry(hass, entry)

        assert result is False
        # Services should still be registered since unload failed
        for svc in all_services:
            assert hass.services.has_service(DOMAIN, svc)
