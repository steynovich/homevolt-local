"""Binary sensor platform for Homevolt Local integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HomevoltConfigEntry
from ._compat import BinarySensorDeviceClass
from .const import DOMAIN
from .coordinator import HomevoltCoordinator
from .device import get_ecu_device_info, get_local_ems

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to avoid overwhelming the device
PARALLEL_UPDATES = 1


def _get_param_bool(params: list[dict[str, Any]], name: str) -> bool | None:
    """Extract a boolean parameter value from params list."""
    if not isinstance(params, list):
        return None
    for param in params:
        if param.get("name") == name:
            value = param.get("value")
            # Handle array format: value is [true] or [false]
            if isinstance(value, list) and len(value) > 0:
                value = value[0]
            return value in (True, "true", 1, "1")
    return None


@dataclass(frozen=True, kw_only=True)
class HomevoltBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Homevolt binary sensor entity."""

    param_key: str


BINARY_SENSORS: tuple[HomevoltBinarySensorEntityDescription, ...] = (
    HomevoltBinarySensorEntityDescription(
        key="mqtt_valid",
        translation_key="mqtt_valid",
        param_key="mqtt_valid",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomevoltConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homevolt binary sensors based on a config entry."""
    coordinator = entry.runtime_data

    entities: list[BinarySensorEntity] = [
        HomevoltBinarySensor(coordinator, description) for description in BINARY_SENSORS
    ]

    # Add WiFi and LTE connected sensors (uses status.wifi_status and status.lte_status)
    entities.append(WiFiConnectedBinarySensor(coordinator))
    entities.append(LTEConnectedBinarySensor(coordinator))

    # Alarm sensors are per unit: each Homevolt reports its own, on its own device. A leader's
    # follower units get theirs from their own config entry.
    entities.append(AlarmBinarySensor(coordinator))

    async_add_entities(entities)
    _async_remove_follower_alarms(hass, entry, coordinator.device_id)


def _async_remove_follower_alarms(
    hass: HomeAssistant, entry: HomevoltConfigEntry, own_id: str
) -> None:
    """Remove the follower Alarm sensors (and their devices) older versions added to a leader.

    They had unique IDs ``{leader_id}_{ecu_id}_alarm`` and sat on a device keyed by the
    follower's ecu_id, which HA never merged with the follower's own device.
    """
    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if (
            entity.domain == "binary_sensor"
            and entity.unique_id.startswith(f"{own_id}_")
            and entity.unique_id.endswith("_alarm")
            and entity.unique_id != f"{own_id}_alarm"
        ):
            entity_registry.async_remove(entity.entity_id)

    device_registry = dr.async_get(hass)
    kept = {(DOMAIN, own_id), (DOMAIN, f"{own_id}_cluster")}
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if not device.identifiers & kept and not er.async_entries_for_device(
            entity_registry, device.id
        ):
            device_registry.async_remove_device(device.id)


class HomevoltBinarySensor(CoordinatorEntity[HomevoltCoordinator], BinarySensorEntity):
    """Representation of a Homevolt binary sensor."""

    entity_description: HomevoltBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        description: HomevoltBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        self._attr_device_info = get_ecu_device_info(coordinator)

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        params = self.coordinator.data.get("params", [])
        return _get_param_bool(params, self.entity_description.param_key)


class WiFiConnectedBinarySensor(CoordinatorEntity[HomevoltCoordinator], BinarySensorEntity):
    """Representation of WiFi connected status from status.json."""

    _attr_has_entity_name = True
    _attr_translation_key = "wifi_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: HomevoltCoordinator) -> None:
        """Initialize the WiFi connected sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_wifi_connected"
        self._attr_device_info = get_ecu_device_info(coordinator)

    @property
    def is_on(self) -> bool | None:
        """Return true if WiFi is connected."""
        status = self.coordinator.data.get("status", {})
        wifi_status = status.get("wifi_status", {})
        connected = wifi_status.get("connected")
        if connected is None:
            return None
        return connected in (True, "true", 1, "1")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        status = self.coordinator.data.get("status", {})
        wifi_status = status.get("wifi_status", {})
        ssid = wifi_status.get("ssid")
        if ssid:
            return {"ssid": ssid}
        return None


class LTEConnectedBinarySensor(CoordinatorEntity[HomevoltCoordinator], BinarySensorEntity):
    """Representation of LTE connected status from status.json."""

    _attr_has_entity_name = True
    _attr_translation_key = "lte_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: HomevoltCoordinator) -> None:
        """Initialize the LTE connected sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_lte_connected"
        self._attr_device_info = get_ecu_device_info(coordinator)

    @property
    def is_on(self) -> bool | None:
        """Return true if LTE is connected (operator_name is set)."""
        status = self.coordinator.data.get("status", {})
        lte_status = status.get("lte_status", {})
        operator_name = lte_status.get("operator_name")
        if operator_name is None:
            return None
        return bool(operator_name)  # True if non-empty string

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        status = self.coordinator.data.get("status", {})
        lte_status = status.get("lte_status", {})
        operator_name = lte_status.get("operator_name")
        if operator_name:
            return {"operator": operator_name}
        return None


def _string_list(value: Any) -> list[str]:
    """Return value if it is a list, otherwise an empty list."""
    return list(value) if isinstance(value, list) else []


class AlarmBinarySensor(CoordinatorEntity[HomevoltCoordinator], BinarySensorEntity):
    """Problem sensor that is on while the unit reports active alarms.

    Warnings and info messages are exposed as attributes only and do not
    influence the state.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "alarm"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: HomevoltCoordinator) -> None:
        """Initialize the alarm sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_alarm"
        self._attr_device_info = get_ecu_device_info(coordinator)

    def _ems_data(self) -> dict[str, Any]:
        """Return ems_data of the local unit."""
        ems_payload = self.coordinator.data.get("ems", {}) if self.coordinator.data else {}
        ems_data = get_local_ems(ems_payload).get("ems_data", {})
        return ems_data if isinstance(ems_data, dict) else {}

    @property
    def available(self) -> bool:
        """Return False when the device does not report a valid alarm list."""
        return super().available and isinstance(self._ems_data().get("alarm_str"), list)

    @property
    def is_on(self) -> bool | None:
        """Return true if at least one alarm is active."""
        alarms = self._ems_data().get("alarm_str")
        if not isinstance(alarms, list):
            return None
        return len(alarms) > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the active alarms, warnings and info messages."""
        ems_data = self._ems_data()
        return {
            "alarms": _string_list(ems_data.get("alarm_str")),
            "warnings": _string_list(ems_data.get("warning_str")),
            "info": _string_list(ems_data.get("info_str")),
        }
