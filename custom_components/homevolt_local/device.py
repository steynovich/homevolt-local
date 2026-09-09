"""Device helpers for Homevolt Local integration."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

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
