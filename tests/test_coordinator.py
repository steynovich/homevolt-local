"""Tests for Homevolt Local data coordinator."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.homevolt_local.api import HomevoltApiError
from custom_components.homevolt_local.coordinator import (
    HOSTNAME_PATTERN,
    HomevoltCoordinator,
    _extract_device_id_from_host,
    _extract_ecu_id,
)


class TestExtractDeviceIdFromHost:
    """Test _extract_device_id_from_host function."""

    def test_extract_from_homevolt_dash_hostname(self) -> None:
        """Test extracting device ID from homevolt-xxxx.local hostname."""
        result = _extract_device_id_from_host("homevolt-abc123.local")
        assert result == "abc123"

    def test_extract_from_homevolt_underscore_hostname(self) -> None:
        """Test extracting device ID from homevolt_xxxx hostname."""
        result = _extract_device_id_from_host("homevolt_def456")
        assert result == "def456"

    def test_extract_from_homevolt_no_separator(self) -> None:
        """Test extracting device ID from homevoltxxxx hostname."""
        result = _extract_device_id_from_host("homevolt789ghi")
        assert result == "789ghi"

    def test_no_match_for_ip_address(self) -> None:
        """Test no match for IP address."""
        result = _extract_device_id_from_host("192.168.1.100")
        assert result is None

    def test_no_match_for_unrelated_hostname(self) -> None:
        """Test no match for unrelated hostname."""
        result = _extract_device_id_from_host("mydevice.local")
        assert result is None

    def test_extract_with_subdomain(self) -> None:
        """Test extracting from hostname with subdomain."""
        result = _extract_device_id_from_host("homevolt-test.home.local")
        assert result == "test"


class TestExtractEcuId:
    """Test _extract_ecu_id function."""

    def test_extract_from_nested_format(self) -> None:
        """Test extracting ecu_id from nested EMS format."""
        ems_data = {"ems": [{"ecu_id": "ECU12345"}]}
        result = _extract_ecu_id(ems_data)
        assert result == "ECU12345"

    def test_extract_from_flat_format(self) -> None:
        """Test extracting ecu_id from flat format."""
        ems_data = {"ecu_id": "ECU67890"}
        result = _extract_ecu_id(ems_data)
        assert result == "ECU67890"

    def test_extract_from_list_format(self) -> None:
        """Test extracting ecu_id from list format."""
        ems_data = [{"ecu_id": "ECU11111"}]
        result = _extract_ecu_id(ems_data)
        assert result == "ECU11111"

    def test_no_ecu_id_in_data(self) -> None:
        """Test when no ecu_id is present."""
        ems_data = {"ems": [{"other_field": "value"}]}
        result = _extract_ecu_id(ems_data)
        assert result is None

    def test_empty_ems_list(self) -> None:
        """Test with empty EMS list."""
        ems_data = {"ems": []}
        result = _extract_ecu_id(ems_data)
        assert result is None

    def test_empty_dict(self) -> None:
        """Test with empty dict."""
        ems_data = {}
        result = _extract_ecu_id(ems_data)
        assert result is None

    def test_empty_list(self) -> None:
        """Test with empty list."""
        ems_data = []
        result = _extract_ecu_id(ems_data)
        assert result is None


class TestHomevoltCoordinator:
    """Test HomevoltCoordinator class."""

    @pytest.fixture
    def mock_api(self) -> MagicMock:
        """Create a mock API client."""
        api = MagicMock()
        api.get_all_data = AsyncMock(return_value={})
        return api

    @pytest.fixture
    def coordinator(self, hass: HomeAssistant, mock_api: MagicMock) -> HomevoltCoordinator:
        """Create a coordinator for testing."""
        initial_data = {
            "ems": {"ems": [{"ecu_id": "test123"}]},
            "status": {"firmware": {"esp": "1.0.0"}},
            "params": [],
        }
        return HomevoltCoordinator(hass, mock_api, "homevolt-test.local", initial_data)

    async def test_device_id_from_ecu_id(self, coordinator: HomevoltCoordinator) -> None:
        """Test device_id uses ecu_id when available."""
        coordinator._initial_data = {"ems": {"ems": [{"ecu_id": "ECU12345"}]}}
        assert coordinator.device_id == "ECU12345"

    async def test_device_id_from_hostname(self, hass: HomeAssistant, mock_api: MagicMock) -> None:
        """Test device_id falls back to hostname."""
        coordinator = HomevoltCoordinator(hass, mock_api, "homevolt-fallback.local", {"ems": {}})
        assert coordinator.device_id == "fallback"

    async def test_device_id_default(self, hass: HomeAssistant, mock_api: MagicMock) -> None:
        """Test device_id uses default when nothing matches."""
        coordinator = HomevoltCoordinator(hass, mock_api, "192.168.1.100", {"ems": {}})
        assert coordinator.device_id == "homevolt"

    async def test_device_name_from_params(self, hass: HomeAssistant, mock_api: MagicMock) -> None:
        """Test device_name uses mdns instance name from params."""
        coordinator = HomevoltCoordinator(
            hass,
            mock_api,
            "homevolt.local",
            {
                "ems": {"ems": [{"ecu_id": "test"}]},
                "params": [{"name": "ecu_mdns_instance_name", "value": "My Battery"}],
            },
        )
        assert coordinator.device_name == "My Battery"

    async def test_device_name_from_device_id(self, coordinator: HomevoltCoordinator) -> None:
        """Test device_name falls back to device ID."""
        coordinator._initial_data = {
            "ems": {"ems": [{"ecu_id": "ABC123"}]},
            "params": [],
        }
        assert coordinator.device_name == "Homevolt ABC123"

    async def test_device_name_default(self, hass: HomeAssistant, mock_api: MagicMock) -> None:
        """Test device_name uses default."""
        coordinator = HomevoltCoordinator(
            hass, mock_api, "192.168.1.100", {"ems": {}, "params": []}
        )
        assert coordinator.device_name == "Homevolt Battery"

    async def test_firmware_version(self, coordinator: HomevoltCoordinator) -> None:
        """Test firmware_version extraction."""
        coordinator._initial_data = {
            "status": {"firmware": {"esp": "2.1.0"}},
        }
        assert coordinator.firmware_version == "2.1.0"

    async def test_firmware_version_none(self, hass: HomeAssistant, mock_api: MagicMock) -> None:
        """Test firmware_version returns None when not available."""
        coordinator = HomevoltCoordinator(hass, mock_api, "homevolt.local", {"status": {}})
        assert coordinator.firmware_version is None

    async def test_async_update_data_success(
        self, coordinator: HomevoltCoordinator, mock_api: MagicMock
    ) -> None:
        """Test successful data update."""
        mock_api.get_all_data = AsyncMock(return_value={"status": "updated"})

        result = await coordinator._async_update_data()

        assert result == {"status": "updated"}
        mock_api.get_all_data.assert_awaited_once()

    async def test_async_update_data_api_error(
        self, coordinator: HomevoltCoordinator, mock_api: MagicMock
    ) -> None:
        """Test data update with API error raises UpdateFailed."""
        mock_api.get_all_data = AsyncMock(side_effect=HomevoltApiError("Connection error"))

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    async def test_device_id_uses_data_when_available(
        self, coordinator: HomevoltCoordinator
    ) -> None:
        """Test device_id prefers coordinator.data over initial_data."""
        # Simulate data being set after first update
        coordinator.data = {"ems": {"ems": [{"ecu_id": "UPDATED_ID"}]}}

        assert coordinator.device_id == "UPDATED_ID"

    async def test_device_name_uses_data_when_available(
        self, coordinator: HomevoltCoordinator
    ) -> None:
        """Test device_name prefers coordinator.data over initial_data."""
        coordinator.data = {
            "ems": {"ems": [{"ecu_id": "test"}]},
            "params": [{"name": "ecu_mdns_instance_name", "value": "Updated Name"}],
        }

        assert coordinator.device_name == "Updated Name"


class TestLeaderDetection:
    """Test is_leader property."""

    @pytest.fixture
    def mock_api(self) -> MagicMock:
        """Create a mock API client."""
        api = MagicMock()
        api.get_all_data = AsyncMock(return_value={})
        return api

    @pytest.fixture
    def coordinator(self, hass: HomeAssistant, mock_api: MagicMock) -> HomevoltCoordinator:
        """Create a coordinator for testing."""
        initial_data = {
            "ems": {"ems": [{"ecu_id": "test123"}]},
            "status": {"firmware": {"esp": "1.0.0"}},
            "params": [],
        }
        return HomevoltCoordinator(hass, mock_api, "homevolt-test.local", initial_data)

    async def test_is_leader_when_multiple_ems_units(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test is_leader returns True when ems list has more than one unit."""
        coordinator = HomevoltCoordinator(
            hass,
            mock_api,
            "homevolt.local",
            {
                "ems": {
                    "ems": [
                        {"ecu_id": "leader"},
                        {"ecu_id": "follower1"},
                    ],
                },
            },
        )
        assert coordinator.is_leader is True

    async def test_is_leader_with_three_units(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test is_leader returns True with three or more units."""
        coordinator = HomevoltCoordinator(
            hass,
            mock_api,
            "homevolt.local",
            {
                "ems": {
                    "ems": [
                        {"ecu_id": "leader"},
                        {"ecu_id": "follower1"},
                        {"ecu_id": "follower2"},
                    ],
                },
            },
        )
        assert coordinator.is_leader is True

    async def test_is_follower_when_single_ems_unit(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test is_leader returns False when ems list has only one unit."""
        coordinator = HomevoltCoordinator(
            hass,
            mock_api,
            "homevolt.local",
            {
                "ems": {"ems": [{"ecu_id": "standalone"}]},
            },
        )
        assert coordinator.is_leader is False

    async def test_is_follower_when_ems_list_empty(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test is_leader returns False when ems list is empty."""
        coordinator = HomevoltCoordinator(
            hass,
            mock_api,
            "homevolt.local",
            {
                "ems": {"ems": []},
            },
        )
        assert coordinator.is_leader is False

    async def test_is_follower_when_ems_key_missing(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test is_leader returns False when ems key is missing from dict."""
        coordinator = HomevoltCoordinator(
            hass,
            mock_api,
            "homevolt.local",
            {
                "ems": {},
            },
        )
        assert coordinator.is_leader is False

    async def test_is_follower_when_ems_not_dict(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test is_leader returns False when EMS data is not a dict."""
        coordinator = HomevoltCoordinator(
            hass,
            mock_api,
            "homevolt.local",
            {
                "ems": ["invalid", "format"],
            },
        )
        assert coordinator.is_leader is False

    async def test_is_follower_when_ems_list_not_list(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test is_leader returns False when ems value is not a list."""
        coordinator = HomevoltCoordinator(
            hass,
            mock_api,
            "homevolt.local",
            {
                "ems": {"ems": "not_a_list"},
            },
        )
        assert coordinator.is_leader is False

    async def test_is_follower_when_ems_missing(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test is_leader returns False when EMS data is missing entirely."""
        coordinator = HomevoltCoordinator(
            hass,
            mock_api,
            "homevolt.local",
            {},
        )
        assert coordinator.is_leader is False

    async def test_is_leader_uses_data_over_initial(self, coordinator: HomevoltCoordinator) -> None:
        """Test is_leader uses data over initial_data when available."""
        # Initial data has single unit (follower/standalone)
        coordinator._initial_data["ems"] = {"ems": [{"ecu_id": "test"}]}
        # Current data has multiple units (leader)
        coordinator.data = {
            "ems": {
                "ems": [
                    {"ecu_id": "leader"},
                    {"ecu_id": "follower1"},
                ],
            },
        }
        assert coordinator.is_leader is True


class TestClusterProperties:
    """Test cluster_id and cluster_name properties."""

    @pytest.fixture
    def mock_api(self) -> MagicMock:
        """Create a mock API client."""
        api = MagicMock()
        api.get_all_data = AsyncMock(return_value={})
        return api

    async def test_cluster_id(self, hass: HomeAssistant, mock_api: MagicMock) -> None:
        """Test cluster_id returns correct format."""
        coordinator = HomevoltCoordinator(
            hass,
            mock_api,
            "homevolt.local",
            {
                "ems": {"ems": [{"ecu_id": "test123"}]},
                "params": [],
            },
        )
        assert coordinator.cluster_id == "test123_cluster"

    async def test_cluster_name(self, hass: HomeAssistant, mock_api: MagicMock) -> None:
        """Test cluster_name returns correct format."""
        coordinator = HomevoltCoordinator(
            hass,
            mock_api,
            "homevolt.local",
            {
                "ems": {"ems": [{"ecu_id": "test"}]},
                "params": [{"name": "ecu_mdns_instance_name", "value": "My Battery"}],
            },
        )
        assert coordinator.cluster_name == "My Battery Cluster"


class TestHostnamePattern:
    """Test hostname pattern regex."""

    def test_matches_homevolt_dash(self) -> None:
        """Test pattern matches homevolt-xxx."""
        match = HOSTNAME_PATTERN.search("homevolt-abc123")
        assert match is not None
        assert match.group(1) == "abc123"

    def test_matches_homevolt_underscore(self) -> None:
        """Test pattern matches homevolt_xxx."""
        match = HOSTNAME_PATTERN.search("homevolt_xyz789")
        assert match is not None
        assert match.group(1) == "xyz789"

    def test_matches_homevolt_no_separator(self) -> None:
        """Test pattern matches homevoltxxx."""
        match = HOSTNAME_PATTERN.search("homevolt123abc")
        assert match is not None
        assert match.group(1) == "123abc"

    def test_case_insensitive_not_default(self) -> None:
        """Test pattern is case sensitive by default."""
        match = HOSTNAME_PATTERN.search("HOMEVOLT-ABC123")
        assert match is None

    def test_matches_in_longer_string(self) -> None:
        """Test pattern matches within longer hostname."""
        match = HOSTNAME_PATTERN.search("http://homevolt-test.local/api")
        assert match is not None
        assert match.group(1) == "test"
