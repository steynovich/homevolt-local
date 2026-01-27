"""Diagnostics support for Homevolt Local."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import HomevoltConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME, "ecu_id", "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HomevoltConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    coordinator_info: dict[str, Any] = {
        "device_id": coordinator.device_id,
        "device_name": coordinator.device_name,
        "firmware_version": coordinator.firmware_version,
        "is_leader": coordinator.is_leader,
        "last_update_success": coordinator.last_update_success,
        "data": async_redact_data(coordinator.data, TO_REDACT) if coordinator.data else None,
    }

    # Add cluster info for leader devices
    if coordinator.is_leader:
        coordinator_info["cluster_id"] = coordinator.cluster_id
        coordinator_info["cluster_name"] = coordinator.cluster_name

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
            "unique_id": entry.unique_id,
        },
        "coordinator": coordinator_info,
    }
