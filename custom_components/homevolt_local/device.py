"""Device helpers for Homevolt Local integration."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, MANUFACTURER, MODEL, MODEL_CLUSTER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import HomevoltCoordinator


class DeviceType(Enum):
    """Device types for entities."""

    ECU = "ecu"
    CLUSTER = "cluster"


def get_local_ems(data: dict[str, Any]) -> dict[str, Any]:
    """Get local EMS entry (where ecu_host is empty)."""
    ems_list = data.get("ems", [])
    if isinstance(ems_list, list):
        for ems in ems_list:
            if isinstance(ems, dict) and not ems.get("ecu_host"):
                return ems
    return {}


def get_ems_by_ecu_id(data: dict[str, Any], ecu_id: str) -> dict[str, Any]:
    """Get the EMS entry with the given ecu_id (list order is not stable)."""
    ems_list = data.get("ems", [])
    if isinstance(ems_list, list):
        for ems in ems_list:
            if isinstance(ems, dict) and ems.get("ecu_id") == ecu_id:
                return ems
    return {}


def get_follower_ecu_ids(data: dict[str, Any], own_id: str) -> list[str]:
    """Return ecu_ids of other units in the ems list, in first-seen order."""
    ems_list = data.get("ems", []) if data else []
    ids: list[str] = []
    if isinstance(ems_list, list):
        for ems in ems_list:
            if not isinstance(ems, dict):
                continue
            ecu_id = ems.get("ecu_id")
            if ecu_id and ecu_id != own_id and ems.get("ecu_host") and ecu_id not in ids:
                ids.append(ecu_id)
    return ids


def get_ecu_device_info(coordinator: HomevoltCoordinator) -> DeviceInfo:
    """Get device info for the ECU device."""
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.device_id)},
        name=coordinator.device_name,
        manufacturer=MANUFACTURER,
        model=MODEL,
        sw_version=coordinator.firmware_version,
    )


def async_register_ecu_device(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: HomevoltCoordinator
) -> str:
    """Register the ECU device and return its device registry entry id.

    The cluster device links to the ECU device through ``via_device_id``, which needs
    the registry entry id, so the ECU device must exist before the platforms are set up.
    """
    device_registry = dr.async_get(hass)
    return device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        **get_ecu_device_info(coordinator),
    ).id


def get_cluster_device_info(coordinator: HomevoltCoordinator) -> DeviceInfo:
    """Get device info for the Cluster device.

    The cluster device is linked to the ECU device via via_device_id, which is
    populated by async_register_ecu_device during setup.
    """
    device_info = DeviceInfo(
        identifiers={(DOMAIN, coordinator.cluster_id)},
        name=coordinator.cluster_name,
        manufacturer=MANUFACTURER,
        model=MODEL_CLUSTER,
    )
    if coordinator.ecu_device_entry_id is not None:
        device_info["via_device_id"] = coordinator.ecu_device_entry_id
    return device_info
