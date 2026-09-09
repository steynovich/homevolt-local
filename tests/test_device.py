"""Tests for Homevolt Local device helpers."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homevolt_local.const import DOMAIN, MANUFACTURER, MODEL, MODEL_CLUSTER
from custom_components.homevolt_local.coordinator import HomevoltCoordinator
from custom_components.homevolt_local.device import (
    DeviceType,
    async_register_ecu_device,
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

        coordinator.ecu_device_entry_id = "ecu-registry-id"

        device_info = get_cluster_device_info(coordinator)

        assert device_info["identifiers"] == {(DOMAIN, "test123_cluster")}
        assert device_info["name"] == "My Battery Cluster"
        assert device_info["manufacturer"] == MANUFACTURER
        assert device_info["model"] == MODEL_CLUSTER
        assert device_info["via_device_id"] == "ecu-registry-id"

    async def test_get_cluster_device_info_without_ecu_id(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test via_device_id is omitted when the ECU device is not registered yet."""
        coordinator = HomevoltCoordinator(
            hass,
            mock_api,
            "homevolt.local",
            {"ems": {"ems": [{"ecu_id": "test123"}]}, "params": []},
        )

        assert coordinator.ecu_device_entry_id is None

        device_info = get_cluster_device_info(coordinator)

        assert "via_device_id" not in device_info

    async def test_register_ecu_device(self, hass: HomeAssistant, mock_api: MagicMock) -> None:
        """Test async_register_ecu_device creates the device and returns its entry id."""
        entry = MockConfigEntry(domain=DOMAIN, data={})
        entry.add_to_hass(hass)
        coordinator = HomevoltCoordinator(
            hass,
            mock_api,
            "homevolt.local",
            {
                "ems": {"ems": [{"ecu_id": "ecu456"}]},
                "status": {"firmware": {"esp": "1.2.3"}},
                "params": [],
            },
        )

        device_entry_id = async_register_ecu_device(hass, entry, coordinator)

        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get_device_by_identifier(
            (DOMAIN, "ecu456"), entry.entry_id
        )
        assert device_entry is not None
        assert device_entry.id == device_entry_id
        assert device_entry.model == MODEL
        assert device_entry.sw_version == "1.2.3"

    async def test_cluster_device_links_to_ecu(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> None:
        """Test cluster device is linked to the registered ECU device."""
        entry = MockConfigEntry(domain=DOMAIN, data={})
        entry.add_to_hass(hass)
        coordinator = HomevoltCoordinator(
            hass,
            mock_api,
            "homevolt.local",
            {
                "ems": {"ems": [{"ecu_id": "ecu456"}]},
                "params": [],
            },
        )

        coordinator.ecu_device_entry_id = async_register_ecu_device(hass, entry, coordinator)
        cluster_info = get_cluster_device_info(coordinator)

        # via_device_id should point to the registry entry of the ECU device
        device_registry = dr.async_get(hass)
        ecu_identifier = next(iter(get_ecu_device_info(coordinator)["identifiers"]))
        ecu_entry = device_registry.async_get_device_by_identifier(ecu_identifier, entry.entry_id)
        assert ecu_entry is not None
        assert cluster_info["via_device_id"] == ecu_entry.id
