"""Select platform for Homevolt Local integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
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


def _get_param_string(params: list[dict[str, Any]], name: str) -> str | None:
    """Extract a string parameter value from params list."""
    if not isinstance(params, list):
        return None
    for param in params:
        if param.get("name") == name:
            value = param.get("value")
            # Handle array format: value is ["string"]
            if isinstance(value, list) and len(value) > 0:
                value = value[0]
            if isinstance(value, str):
                return value
    return None


@dataclass(frozen=True, kw_only=True)
class HomevoltSelectEntityDescription(SelectEntityDescription):
    """Describes a Homevolt select entity."""

    param_key: str


SELECTS: tuple[HomevoltSelectEntityDescription, ...] = (
    HomevoltSelectEntityDescription(
        key="ledstrip_mode",
        translation_key="ledstrip_mode",
        param_key="ledstrip_mode",
        options=["unset", "off", "on", "soc", "dem", "ser"],
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomevoltConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homevolt select entities based on a config entry."""
    coordinator = entry.runtime_data

    entities = [HomevoltSelect(coordinator, description) for description in SELECTS]

    async_add_entities(entities)


class HomevoltSelect(CoordinatorEntity[HomevoltCoordinator], SelectEntity):
    """Representation of a Homevolt select entity."""

    entity_description: HomevoltSelectEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        description: HomevoltSelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        self._attr_device_info = get_ecu_device_info(coordinator)

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        params = self.coordinator.data.get("params", [])
        value = _get_param_string(params, self.entity_description.param_key)
        # Return "unset" if empty string or missing
        if not value:
            return "unset"
        # Return None if not in options (invalid value)
        options = self.entity_description.options
        if options is None or value not in options:
            return None
        return value

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.coordinator.api.set_param(self.entity_description.param_key, option)
        await self.coordinator.async_request_refresh()
