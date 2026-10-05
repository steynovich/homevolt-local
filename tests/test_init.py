"""Tests for Homevolt Local integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components.homevolt_local import async_unload_entry
from custom_components.homevolt_local.api import (
    HomevoltAuthError,
    HomevoltConnectionError,
    HomevoltRateLimitError,
)
from custom_components.homevolt_local.const import DOMAIN
from custom_components.homevolt_local.services import (
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
)


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
