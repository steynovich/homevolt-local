"""Tests for Homevolt Local device helpers."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.homevolt_local.const import DOMAIN, MANUFACTURER, MODEL, MODEL_CLUSTER
from custom_components.homevolt_local.coordinator import HomevoltCoordinator
from custom_components.homevolt_local.device import (
    DeviceType,
    get_cluster_device_info,
    get_ecu_device_info,
)


class TestDeviceType:
    """Test DeviceType enum."""

    def test_device_type_values(self) -> None:
        """Test DeviceType enum values."""
        assert DeviceType.ECU.value == "ecu"
        assert DeviceType.CLUSTER.value == "cluster"

    def test_device_type_members(self) -> None:
        """Test DeviceType enum members."""
        assert len(DeviceType) == 2


class TestDeviceInfoHelpers:
    """Test device info helper functions."""

    @pytest.fixture
    def mock_api(self) -> MagicMock:
        """Create a mock API client."""
        api = MagicMock()
        api.get_all_data = AsyncMock(return_value={})
        return api

    async def test_get_ecu_device_info(self, hass: HomeAssistant, mock_api: MagicMock) -> None:
        """Test get_ecu_device_info returns correct DeviceInfo."""
        coordinator = HomevoltCoordinator(
            hass,
            mock_api,
            "homevolt.local",
            {
                "ems": {"ems": [{"ecu_id": "test123"}]},
                "status": {"firmware": {"esp": "1.2.3"}},
                "params": [{"name": "ecu_mdns_instance_name", "value": "My Battery"}],
            },
        )

        device_info = get_ecu_device_info(coordinator)

        assert device_info["identifiers"] == {(DOMAIN, "test123")}
        assert device_info["name"] == "My Battery"
        assert device_info["manufacturer"] == MANUFACTURER
        assert device_info["model"] == MODEL
        assert device_info["sw_version"] == "1.2.3"

    async def test_get_cluster_device_info(self, hass: HomeAssistant, mock_api: MagicMock) -> None:
        """Test get_cluster_device_info returns correct DeviceInfo."""
        coordinator = HomevoltCoordinator(
            hass,
            mock_api,
            "homevolt.local",
            {
                "ems": {"ems": [{"ecu_id": "test123"}]},
                "status": {"firmware": {"esp": "1.2.3"}},
                "params": [{"name": "ecu_mdns_instance_name", "value": "My Battery"}],
            },
        )

        device_info = get_cluster_device_info(coordinator)

        assert device_info["identifiers"] == {(DOMAIN, "test123_cluster")}
        assert device_info["name"] == "My Battery Cluster"
        assert device_info["manufacturer"] == MANUFACTURER
        assert device_info["model"] == MODEL_CLUSTER
        assert device_info["via_device"] == (DOMAIN, "test123")

    async def test_cluster_device_links_to_ecu(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test cluster device is linked to ECU device via via_device."""
        coordinator = HomevoltCoordinator(
            hass,
            mock_api,
            "homevolt.local",
            {
                "ems": {"ems": [{"ecu_id": "ecu456"}]},
                "params": [],
            },
        )

        ecu_info = get_ecu_device_info(coordinator)
        cluster_info = get_cluster_device_info(coordinator)

        # via_device should point to the ECU device identifier
        ecu_identifier = list(ecu_info["identifiers"])[0]
        assert cluster_info["via_device"] == ecu_identifier
