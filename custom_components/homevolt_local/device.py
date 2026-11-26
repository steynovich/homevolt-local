"""Device helpers for Homevolt Local integration."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, MANUFACTURER, MODEL, MODEL_CLUSTER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import HomevoltCoordinator


class _DeviceFields(TypedDict):
    """Device fields shared by ``DeviceInfo`` and ``async_get_or_create``.

    Since HA 2026.12 ``DeviceInfo`` is a dataclass, and unpacking it with ``**`` or
    setting keys on it is deprecated. Building both from one plain mapping works on
    the TypedDict and the dataclass ``DeviceInfo`` alike.
    """

    identifiers: set[tuple[str, str]]
    name: str
    manufacturer: str
    model: str
    sw_version: NotRequired[str | None]
    via_device_id: NotRequired[str]


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


def _ecu_device_fields(coordinator: HomevoltCoordinator) -> _DeviceFields:
    """Return the ECU device fields."""
    return {
        "identifiers": {(DOMAIN, coordinator.device_id)},
        "name": coordinator.device_name,
        "manufacturer": MANUFACTURER,
        "model": MODEL,
        "sw_version": coordinator.firmware_version,
    }


def get_ecu_device_info(coordinator: HomevoltCoordinator) -> DeviceInfo:
    """Get device info for the ECU device."""
    # mypy rejects ** expansion into the TypedDict DeviceInfo of HA < 2026.12, but not
    # into the dataclass; drop the ignore once the minimum HA version is 2026.12
    return DeviceInfo(**_ecu_device_fields(coordinator))  # type: ignore[typeddict-item, unused-ignore]


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
        **_ecu_device_fields(coordinator),
    ).id


def get_cluster_device_info(coordinator: HomevoltCoordinator) -> DeviceInfo:
    """Get device info for the Cluster device.

    The cluster device is linked to the ECU device via via_device_id, which is
    populated by async_register_ecu_device during setup.
    """
    fields: _DeviceFields = {
        "identifiers": {(DOMAIN, coordinator.cluster_id)},
        "name": coordinator.cluster_name,
        "manufacturer": MANUFACTURER,
        "model": MODEL_CLUSTER,
    }
    if coordinator.ecu_device_entry_id is not None:
        fields["via_device_id"] = coordinator.ecu_device_entry_id
    return DeviceInfo(**fields)  # type: ignore[typeddict-item, unused-ignore]
