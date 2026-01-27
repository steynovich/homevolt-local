"""Switch platform for Homevolt Local integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
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
    for param in params:
        if param.get("name") == name:
            value = param.get("value")
            # Handle array format: value is [true] or [false]
            if isinstance(value, list) and len(value) > 0:
                value = value[0]
            return value in (True, "true", 1, "1")
    return None


@dataclass(frozen=True, kw_only=True)
class HomevoltSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Homevolt switch entity."""

    param_key: str


SWITCHES: tuple[HomevoltSwitchEntityDescription, ...] = (
    HomevoltSwitchEntityDescription(
        key="settings_local",
        translation_key="settings_local",
        param_key="settings_local",
    ),
    HomevoltSwitchEntityDescription(
        key="ota_enable",
        translation_key="ota_enable",
        param_key="ota_enable",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HomevoltSwitchEntityDescription(
        key="ota_enable_esp32",
        translation_key="ota_enable_esp32",
        param_key="ota_enable_esp32",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HomevoltSwitchEntityDescription(
        key="ota_enable_hub_web",
        translation_key="ota_enable_hub_web",
        param_key="ota_enable_hub_web",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HomevoltSwitchEntityDescription(
        key="ota_enable_bg95_m3",
        translation_key="ota_enable_bg95_m3",
        param_key="ota_enable_bg95_m3",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomevoltConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homevolt switches based on a config entry."""
    coordinator = entry.runtime_data

    entities = [HomevoltSwitch(coordinator, description) for description in SWITCHES]

    async_add_entities(entities)


class HomevoltSwitch(CoordinatorEntity[HomevoltCoordinator], SwitchEntity):
    """Representation of a Homevolt switch."""

    entity_description: HomevoltSwitchEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        description: HomevoltSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        self._attr_device_info = get_ecu_device_info(coordinator)

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        params = self.coordinator.data.get("params", [])
        if not isinstance(params, list):
            return None
        return _get_param_bool(params, self.entity_description.param_key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.api.set_param(self.entity_description.param_key, "true")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.api.set_param(self.entity_description.param_key, "false")
        await self.coordinator.async_request_refresh()
