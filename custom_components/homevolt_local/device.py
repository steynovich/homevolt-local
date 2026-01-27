"""Device helpers for Homevolt Local integration."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, MANUFACTURER, MODEL, MODEL_CLUSTER

if TYPE_CHECKING:
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


def get_cluster_device_info(coordinator: HomevoltCoordinator) -> DeviceInfo:
    """Get device info for the Cluster device.

    The cluster device is linked to the ECU device via via_device.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.cluster_id)},
        name=coordinator.cluster_name,
        manufacturer=MANUFACTURER,
        model=MODEL_CLUSTER,
        via_device=(DOMAIN, coordinator.device_id),
    )
