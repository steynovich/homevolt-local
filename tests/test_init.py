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
    HomevoltCommandError,
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


async def test_setup_entry_registers_devices(
    hass: HomeAssistant,
    mock_config_data: dict,
    mock_all_data: dict,
    mock_ems_data_leader: dict,
) -> None:
    """Test setup registers the ECU device and links the cluster device to it."""
    from homeassistant.helpers import device_registry as dr
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    leader_data = {**mock_all_data, "ems": mock_ems_data_leader}

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
        mock_api.test_connection = AsyncMock(return_value=True)
        mock_api.get_all_data = AsyncMock(return_value=leader_data)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data
    device_registry = dr.async_get(hass)

    ecu_device = device_registry.async_get_device_by_identifier((DOMAIN, "test123"), entry.entry_id)
    assert ecu_device is not None
    assert coordinator.ecu_device_entry_id == ecu_device.id

    # The leader payload also creates a cluster device, linked back to the ECU
    cluster_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "test123_cluster"), entry.entry_id
    )
    assert cluster_device is not None
    assert cluster_device.via_device_id == ecu_device.id


class TestAsyncUnloadEntry:
    """Tests for async_unload_entry service cleanup."""

    @pytest.mark.asyncio
    async def test_services_removed_when_last_entry_unloaded(self, hass: HomeAssistant) -> None:
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

        with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
            result = await async_unload_entry(hass, entry)

        assert result is True
        # All services should be removed
        for svc in all_services:
            assert not hass.services.has_service(DOMAIN, svc)

    @pytest.mark.asyncio
    async def test_services_kept_when_other_entries_remain(self, hass: HomeAssistant) -> None:
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

        with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
            result = await async_unload_entry(hass, entry1)

        assert result is True
        # Services should still be registered
        for svc in all_services:
            assert hass.services.has_service(DOMAIN, svc)

    @pytest.mark.asyncio
    async def test_services_not_removed_when_unload_fails(self, hass: HomeAssistant) -> None:
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

        with patch.object(hass.config_entries, "async_unload_platforms", return_value=False):
            result = await async_unload_entry(hass, entry)

        assert result is False
        # Services should still be registered since unload failed
        for svc in all_services:
            assert hass.services.has_service(DOMAIN, svc)


async def test_set_schedule_command_error_is_translated(
    hass: HomeAssistant,
    mock_config_data: dict,
    mock_all_data: dict,
) -> None:
    """Test a failing console command raises a translated HomeAssistantError."""
    from homeassistant.exceptions import HomeAssistantError
    from homeassistant.helpers import device_registry as dr
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain=DOMAIN, data=mock_config_data, unique_id="test123")
    entry.add_to_hass(hass)

    with patch("custom_components.homevolt_local.HomevoltApi", autospec=True) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.test_connection = AsyncMock(return_value=True)
        mock_api.get_all_data = AsyncMock(return_value=mock_all_data)
        mock_api.set_schedule = AsyncMock(side_effect=HomevoltCommandError("bad schedule"))

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        device = dr.async_get(hass).async_get_device_by_identifier(
            (DOMAIN, "test123"), entry.entry_id
        )
        assert device is not None

        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SET_SCHEDULE,
                {
                    "device_id": device.id,
                    "schedule": [{"type": 0, "setpoint": 0}],
                },
                blocking=True,
            )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "command_failed"
    assert exc_info.value.translation_placeholders == {"error": "bad schedule"}


ALL_SERVICES = [
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
    SERVICE_SET_SOLAR_CHARGE,
    SERVICE_SET_SOLAR_CHARGE_DISCHARGE,
]


def _service_data(service: str, device_id: str) -> dict:
    """Build minimal valid service data for a service."""
    data: dict = {"device_id": device_id}
    if service == SERVICE_SET_SCHEDULE:
        data["schedule"] = [{"type": 0, "setpoint": 0}]
    if service == SERVICE_SET_GRID_CHARGE_DISCHARGE:
        data["setpoint"] = 0
    return data


@pytest.mark.parametrize("service", ALL_SERVICES)
async def test_service_unknown_device_raises(
    hass: HomeAssistant,
    mock_config_data: dict,
    mock_all_data: dict,
    service: str,
) -> None:
    """Test every service raises a translated error for an unknown device."""
    from homeassistant.exceptions import HomeAssistantError
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain=DOMAIN, data=mock_config_data, unique_id="test123")
    entry.add_to_hass(hass)

    with patch("custom_components.homevolt_local.HomevoltApi", autospec=True) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.test_connection = AsyncMock(return_value=True)
        mock_api.get_all_data = AsyncMock(return_value=mock_all_data)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN, service, _service_data(service, "no-such-device"), blocking=True
            )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "device_not_found"


async def test_service_device_without_homevolt_entry_raises(
    hass: HomeAssistant,
    mock_config_data: dict,
    mock_all_data: dict,
) -> None:
    """Test a device that belongs to no Homevolt config entry raises a translated error."""
    from homeassistant.exceptions import HomeAssistantError
    from homeassistant.helpers import device_registry as dr
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain=DOMAIN, data=mock_config_data, unique_id="test123")
    entry.add_to_hass(hass)
    other = MockConfigEntry(domain="other_domain")
    other.add_to_hass(hass)

    with patch("custom_components.homevolt_local.HomevoltApi", autospec=True) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.test_connection = AsyncMock(return_value=True)
        mock_api.get_all_data = AsyncMock(return_value=mock_all_data)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        foreign = dr.async_get(hass).async_get_or_create(
            config_entry_id=other.entry_id, identifiers={("other_domain", "x")}
        )

        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN, SERVICE_CLEAR_SCHEDULE, {"device_id": foreign.id}, blocking=True
            )

    assert exc_info.value.translation_key == "config_entry_not_found"
