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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HomevoltConfigEntry
from ._compat import BinarySensorDeviceClass
from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import HomevoltCoordinator
from .device import get_ecu_device_info, get_ems_by_ecu_id, get_follower_ecu_ids, get_local_ems

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

    # Alarm sensors are per-unit (ECU only, never on the cluster device): one for the
    # local unit plus one per follower listed in a leader's ems list, keyed by ecu_id.
    entities.append(AlarmBinarySensor(coordinator))
    entities.extend(
        AlarmBinarySensor(coordinator, ecu_id=ecu_id)
        for ecu_id in get_follower_ecu_ids(coordinator.data, coordinator.device_id)
    )

    async_add_entities(entities)


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
    """Problem sensor that is on while a unit reports active alarms.

    Without ``ecu_id`` it reads the local unit. With ``ecu_id`` (leader only) it reads
    the ems entry with that ecu_id, never by list position, and is attached to the
    device with that ecu_id so it merges with the follower's own config entry.

    Warnings and info messages are exposed as attributes only and do not
    influence the state.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "alarm"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: HomevoltCoordinator, ecu_id: str | None = None) -> None:
        """Initialize the alarm sensor."""
        super().__init__(coordinator)
        self._ecu_id = ecu_id
        if ecu_id is None:
            self._attr_unique_id = f"{coordinator.device_id}_alarm"
            self._attr_device_info = get_ecu_device_info(coordinator)
        else:
            # Distinct from the follower's own "{ecu_id}_alarm" so both entries can coexist.
            self._attr_unique_id = f"{coordinator.device_id}_{ecu_id}_alarm"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, ecu_id)},
                name=f"Homevolt {ecu_id}",
                manufacturer=MANUFACTURER,
                model=MODEL,
            )

    def _ems_data(self) -> dict[str, Any]:
        """Return ems_data of the unit this sensor represents."""
        if self._ecu_id is None:
            unit = get_local_ems(self.coordinator.data)
        else:
            unit = get_ems_by_ecu_id(self.coordinator.data, self._ecu_id)
        ems_data = unit.get("ems_data", {})
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
