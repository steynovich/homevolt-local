"""Data update coordinator for Homevolt Local."""

from __future__ import annotations

import logging
import re
from typing import Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HomevoltApi, HomevoltApiError, HomevoltAuthError, HomevoltRateLimitError
from .const import DOMAIN, ERROR_REPORT_SCAN_INTERVAL, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Pattern to extract device ID from hostname
# Examples: "homevolt-abc123.local" or "homevolt1.domain.com"
HOSTNAME_PATTERN = re.compile(r"homevolt[_-]?([a-zA-Z0-9]+)")


# /error_report.json statuses that count as a problem; "ok" and "unknown" (check not
# applicable) do not.
PROBLEM_STATUSES = frozenset({"error", "warning"})


def _coordinator_error(err: HomevoltApiError, host: str) -> ConfigEntryAuthFailed | UpdateFailed:
    """Translate an API error into the exception a coordinator should raise."""
    if isinstance(err, HomevoltAuthError):
        return ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
            translation_placeholders={"host": host},
        )
    if isinstance(err, HomevoltRateLimitError):
        return ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="rate_limited",
        )
    return UpdateFailed(
        translation_domain=DOMAIN,
        translation_key="cannot_connect",
        translation_placeholders={"host": host},
    )


def _extract_device_id_from_host(host: str) -> str | None:
    """Extract device ID from hostname pattern."""
    match = HOSTNAME_PATTERN.search(host)
    if match:
        return match.group(1)
    return None


def _extract_ecu_id(ems_data: dict[str, Any]) -> str | None:
    """Extract ecu_id from EMS response."""
    # EMS response can be a list of systems or a dict with "ems" key
    if isinstance(ems_data, dict):
        # Handle nested format: {"ems": [{"ecu_id": "..."}]}
        ems_list = ems_data.get("ems", [])
        if isinstance(ems_list, list) and ems_list:
            return cast(str | None, ems_list[0].get("ecu_id"))
        # Handle flat format: {"ecu_id": "..."}
        return cast(str | None, ems_data.get("ecu_id"))
    if isinstance(ems_data, list) and ems_data:
        return ems_data[0].get("ecu_id")
    return None


class HomevoltErrorReportCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Polls /error_report.json and exposes the failing subsystem checks.

    ``data`` is the list of checks whose status is ``error`` or ``warning``, each
    as ``{"subsystem", "check", "status", "message"}``.
    """

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, api: HomevoltApi, host: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} error report",
            update_interval=ERROR_REPORT_SCAN_INTERVAL,
        )
        self.api = api
        self._host = host

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch the report and keep only the problem entries."""
        try:
            report = await self.api.get_error_report()
        except HomevoltApiError as err:
            raise _coordinator_error(err, self._host) from err

        return [
            {
                "subsystem": entry.get("sub_system_name"),
                "check": entry.get("error_name"),
                "status": entry["activated"],
                "message": entry.get("message"),
            }
            for entry in report
            if isinstance(entry, dict) and entry.get("activated") in PROBLEM_STATUSES
        ]


class HomevoltCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Homevolt Local data updates."""

    config_entry: ConfigEntry

    #: Device registry entry id of the ECU device, filled in during setup once the
    #: device has been registered. Used as ``via_device_id`` for the cluster device.
    ecu_device_entry_id: str | None = None

    #: Slower-polling companion coordinator for /error_report.json, set during setup.
    error_report_coordinator: HomevoltErrorReportCoordinator | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        api: HomevoltApi,
        host: str,
        initial_data: dict[str, Any],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api
        self._host = host
        self._initial_data = initial_data

    @property
    def device_id(self) -> str:
        """Return the device ID."""
        # Try to get ecu_id from EMS data
        ems_data = self.data.get("ems", {}) if self.data else self._initial_data.get("ems", {})
        ecu_id = _extract_ecu_id(ems_data)
        if ecu_id:
            return ecu_id

        # Try to extract from hostname
        host_id = _extract_device_id_from_host(self._host)
        if host_id:
            return host_id

        return "homevolt"

    @property
    def device_name(self) -> str:
        """Return the device name."""
        # Try to get user-configured name from params
        # Params is a flat list of {"name": "...", "value": "..."} objects
        params = self.data.get("params", []) if self.data else self._initial_data.get("params", [])
        if isinstance(params, list):
            for param in params:
                if param.get("name") == "ecu_mdns_instance_name":
                    value = param.get("value")
                    if value:
                        return cast(str, value)

        # Fall back to device ID
        device_id = self.device_id
        if device_id and device_id != "homevolt":
            return f"Homevolt {device_id}"
        return "Homevolt Battery"

    @property
    def firmware_version(self) -> str | None:
        """Return the firmware version."""
        status = self.data.get("status", {}) if self.data else self._initial_data.get("status", {})
        firmware = status.get("firmware", {})
        if isinstance(firmware, dict):
            esp_version = firmware.get("esp")
            if esp_version:
                return cast(str, esp_version)
        return None

    @property
    def host(self) -> str:
        """Return the device host."""
        return self._host

    @property
    def is_leader(self) -> bool:
        """Return True if this device is a cluster leader.

        A device is considered a leader if the ems list contains more than one unit,
        meaning it has visibility into other devices in the cluster.
        """
        ems_data = self.data.get("ems", {}) if self.data else self._initial_data.get("ems", {})
        if not isinstance(ems_data, dict):
            return False
        ems_list = ems_data.get("ems", [])
        if not isinstance(ems_list, list):
            return False
        return len(ems_list) > 1

    @property
    def cluster_id(self) -> str:
        """Return the cluster device ID."""
        return f"{self.device_id}_cluster"

    @property
    def cluster_name(self) -> str:
        """Return the cluster device name."""
        return f"{self.device_name} Cluster"

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            return await self.api.get_all_data()
        except HomevoltApiError as err:
            raise _coordinator_error(err, self._host) from err
