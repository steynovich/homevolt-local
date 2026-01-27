"""Binary sensor platform for Homevolt Local integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HomevoltConfigEntry
from .coordinator import HomevoltCoordinator
from .device import get_ecu_device_info

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
