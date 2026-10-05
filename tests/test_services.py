"""Tests for Homevolt Local services."""

from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant

from custom_components.homevolt_local.api import HomevoltCommandError
from custom_components.homevolt_local.const import DOMAIN
from custom_components.homevolt_local.services import (
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
    validate_iso8601_datetime,
)


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


async def _setup_entry(hass: HomeAssistant, mock_config_data: dict, mock_api_class):  # type: ignore[no-untyped-def]
    """Set up a config entry with a mocked API and return (entry, api, device_id)."""
    from homeassistant.helpers import device_registry as dr
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain=DOMAIN, data=mock_config_data, unique_id="test123")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, "test123"), entry.entry_id)
    assert device is not None
    return entry, mock_api_class.return_value, device.id


async def test_reboot_connection_error_is_translated(
    hass: HomeAssistant, mock_config_data: dict, mock_all_data: dict
) -> None:
    """Test reboot translates connection errors instead of leaking raw ones."""
    from homeassistant.exceptions import HomeAssistantError

    from custom_components.homevolt_local.api import HomevoltConnectionError

    with patch("custom_components.homevolt_local.HomevoltApi", autospec=True) as api_class:
        api = api_class.return_value
        api.test_connection = AsyncMock(return_value=True)
        api.get_all_data = AsyncMock(return_value=mock_all_data)
        api.reboot = AsyncMock(side_effect=HomevoltConnectionError("down"))
        _, _, device_id = await _setup_entry(hass, mock_config_data, api_class)

        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN, SERVICE_REBOOT, {"device_id": device_id}, blocking=True
            )

    assert exc_info.value.translation_key == "cannot_connect"
    assert exc_info.value.translation_placeholders == {"host": mock_config_data["host"]}


async def test_reboot_does_not_refresh(
    hass: HomeAssistant, mock_config_data: dict, mock_all_data: dict
) -> None:
    """Test reboot doesn't poll the device that is going down."""
    with patch("custom_components.homevolt_local.HomevoltApi", autospec=True) as api_class:
        api = api_class.return_value
        api.test_connection = AsyncMock(return_value=True)
        api.get_all_data = AsyncMock(return_value=mock_all_data)
        api.reboot = AsyncMock(return_value={})
        _, _, device_id = await _setup_entry(hass, mock_config_data, api_class)
        api.get_all_data.reset_mock()

        await hass.services.async_call(
            DOMAIN, SERVICE_REBOOT, {"device_id": device_id}, blocking=True
        )
        await hass.async_block_till_done()

    api.reboot.assert_awaited_once()
    api.get_all_data.assert_not_awaited()


async def test_set_charge_passes_arguments_and_refreshes(
    hass: HomeAssistant, mock_config_data: dict, mock_all_data: dict
) -> None:
    """Test a setpoint/SOC service forwards its fields to the API."""
    with patch("custom_components.homevolt_local.HomevoltApi", autospec=True) as api_class:
        api = api_class.return_value
        api.test_connection = AsyncMock(return_value=True)
        api.get_all_data = AsyncMock(return_value=mock_all_data)
        api.set_charge = AsyncMock(return_value={})
        _, _, device_id = await _setup_entry(hass, mock_config_data, api_class)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_CHARGE,
            {"device_id": device_id, "setpoint": 500, "min_soc": 10, "max_soc": 90},
            blocking=True,
        )

    api.set_charge.assert_awaited_once_with(setpoint=500, min_soc=10, max_soc=90)
