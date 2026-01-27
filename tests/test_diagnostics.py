"""Tests for Homevolt Local diagnostics."""

from unittest.mock import MagicMock

import pytest
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from custom_components.homevolt_local.const import DOMAIN
from custom_components.homevolt_local.diagnostics import (
    TO_REDACT,
    async_get_config_entry_diagnostics,
)


class TestDiagnostics:
    """Test diagnostics functionality."""

    def test_to_redact_includes_sensitive_fields(self) -> None:
        """Test that TO_REDACT includes all sensitive fields."""
        assert CONF_PASSWORD in TO_REDACT
        assert CONF_USERNAME in TO_REDACT
        assert "ecu_id" in TO_REDACT
        assert "serial_number" in TO_REDACT

    @pytest.fixture
    def mock_entry(self) -> MagicMock:
        """Create a mock config entry."""
        entry = MagicMock()
        entry.entry_id = "test_entry_id"
        entry.version = 1
        entry.domain = DOMAIN
        entry.title = "Homevolt test123"
        entry.unique_id = "test123"
        entry.data = {
            CONF_HOST: "homevolt-test.local",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret_password",
        }
        return entry

    @pytest.fixture
    def mock_coordinator(self) -> MagicMock:
        """Create a mock coordinator."""
        coordinator = MagicMock()
        coordinator.device_id = "test123"
        coordinator.device_name = "My Homevolt"
        coordinator.firmware_version = "1.2.3"
        coordinator.last_update_success = True
        coordinator.data = {
            "ems": {
                "ems": [
                    {
                        "ecu_id": "ECU123456",
                        "serial_number": "SN789",
                        "ems_data": {"soc_avg": 75},
                    }
                ]
            },
            "status": {"up_time": 12345},
        }
        return coordinator

    async def test_diagnostics_output_structure(
        self, hass: HomeAssistant, mock_entry: MagicMock, mock_coordinator: MagicMock
    ) -> None:
        """Test diagnostics returns correct structure."""
        mock_entry.runtime_data = mock_coordinator

        result = await async_get_config_entry_diagnostics(hass, mock_entry)

        assert "entry" in result
        assert "coordinator" in result

    async def test_diagnostics_entry_data(
        self, hass: HomeAssistant, mock_entry: MagicMock, mock_coordinator: MagicMock
    ) -> None:
        """Test diagnostics entry data is correct."""
        mock_entry.runtime_data = mock_coordinator

        result = await async_get_config_entry_diagnostics(hass, mock_entry)

        assert result["entry"]["entry_id"] == "test_entry_id"
        assert result["entry"]["version"] == 1
        assert result["entry"]["domain"] == DOMAIN
        assert result["entry"]["title"] == "Homevolt test123"
        assert result["entry"]["unique_id"] == "test123"

    async def test_diagnostics_redacts_password(
        self, hass: HomeAssistant, mock_entry: MagicMock, mock_coordinator: MagicMock
    ) -> None:
        """Test diagnostics redacts password."""
        mock_entry.runtime_data = mock_coordinator

        result = await async_get_config_entry_diagnostics(hass, mock_entry)

        assert result["entry"]["data"][CONF_PASSWORD] == "**REDACTED**"

    async def test_diagnostics_redacts_username(
        self, hass: HomeAssistant, mock_entry: MagicMock, mock_coordinator: MagicMock
    ) -> None:
        """Test diagnostics redacts username."""
        mock_entry.runtime_data = mock_coordinator

        result = await async_get_config_entry_diagnostics(hass, mock_entry)

        assert result["entry"]["data"][CONF_USERNAME] == "**REDACTED**"

    async def test_diagnostics_keeps_host(
        self, hass: HomeAssistant, mock_entry: MagicMock, mock_coordinator: MagicMock
    ) -> None:
        """Test diagnostics keeps host visible."""
        mock_entry.runtime_data = mock_coordinator

        result = await async_get_config_entry_diagnostics(hass, mock_entry)

        assert result["entry"]["data"][CONF_HOST] == "homevolt-test.local"

    async def test_diagnostics_coordinator_data(
        self, hass: HomeAssistant, mock_entry: MagicMock, mock_coordinator: MagicMock
    ) -> None:
        """Test diagnostics coordinator data is correct."""
        mock_entry.runtime_data = mock_coordinator

        result = await async_get_config_entry_diagnostics(hass, mock_entry)

        assert result["coordinator"]["device_id"] == "test123"
        assert result["coordinator"]["device_name"] == "My Homevolt"
        assert result["coordinator"]["firmware_version"] == "1.2.3"
        assert result["coordinator"]["last_update_success"] is True

    async def test_diagnostics_redacts_ecu_id_in_data(
        self, hass: HomeAssistant, mock_entry: MagicMock, mock_coordinator: MagicMock
    ) -> None:
        """Test diagnostics redacts ecu_id in coordinator data."""
        mock_entry.runtime_data = mock_coordinator

        result = await async_get_config_entry_diagnostics(hass, mock_entry)

        # The ecu_id in the nested data should be redacted
        ems_data = result["coordinator"]["data"]["ems"]["ems"][0]
        assert ems_data["ecu_id"] == "**REDACTED**"

    async def test_diagnostics_redacts_serial_number_in_data(
        self, hass: HomeAssistant, mock_entry: MagicMock, mock_coordinator: MagicMock
    ) -> None:
        """Test diagnostics redacts serial_number in coordinator data."""
        mock_entry.runtime_data = mock_coordinator

        result = await async_get_config_entry_diagnostics(hass, mock_entry)

        ems_data = result["coordinator"]["data"]["ems"]["ems"][0]
        assert ems_data["serial_number"] == "**REDACTED**"

    async def test_diagnostics_with_none_data(
        self, hass: HomeAssistant, mock_entry: MagicMock
    ) -> None:
        """Test diagnostics handles None coordinator data."""
        mock_coordinator = MagicMock()
        mock_coordinator.device_id = "test123"
        mock_coordinator.device_name = "My Homevolt"
        mock_coordinator.firmware_version = None
        mock_coordinator.last_update_success = False
        mock_coordinator.is_leader = True
        mock_coordinator.cluster_id = "test123_cluster"
        mock_coordinator.cluster_name = "My Homevolt Cluster"
        mock_coordinator.data = None
        mock_entry.runtime_data = mock_coordinator

        result = await async_get_config_entry_diagnostics(hass, mock_entry)

        assert result["coordinator"]["data"] is None

    async def test_diagnostics_includes_is_leader(
        self, hass: HomeAssistant, mock_entry: MagicMock, mock_coordinator: MagicMock
    ) -> None:
        """Test diagnostics includes is_leader property."""
        mock_coordinator.is_leader = True
        mock_coordinator.cluster_id = "test123_cluster"
        mock_coordinator.cluster_name = "My Homevolt Cluster"
        mock_entry.runtime_data = mock_coordinator

        result = await async_get_config_entry_diagnostics(hass, mock_entry)

        assert result["coordinator"]["is_leader"] is True

    async def test_diagnostics_includes_cluster_info_for_leader(
        self, hass: HomeAssistant, mock_entry: MagicMock, mock_coordinator: MagicMock
    ) -> None:
        """Test diagnostics includes cluster info for leader devices."""
        mock_coordinator.is_leader = True
        mock_coordinator.cluster_id = "test123_cluster"
        mock_coordinator.cluster_name = "My Homevolt Cluster"
        mock_entry.runtime_data = mock_coordinator

        result = await async_get_config_entry_diagnostics(hass, mock_entry)

        assert result["coordinator"]["cluster_id"] == "test123_cluster"
        assert result["coordinator"]["cluster_name"] == "My Homevolt Cluster"

    async def test_diagnostics_excludes_cluster_info_for_follower(
        self, hass: HomeAssistant, mock_entry: MagicMock, mock_coordinator: MagicMock
    ) -> None:
        """Test diagnostics excludes cluster info for follower devices."""
        mock_coordinator.is_leader = False
        mock_entry.runtime_data = mock_coordinator

        result = await async_get_config_entry_diagnostics(hass, mock_entry)

        assert "cluster_id" not in result["coordinator"]
        assert "cluster_name" not in result["coordinator"]
