"""Number platform for Homevolt Local integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HomevoltConfigEntry
from .coordinator import HomevoltCoordinator
from .device import get_ecu_device_info

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to avoid overwhelming the device
PARALLEL_UPDATES = 1


def _get_param_value(params: list[dict[str, Any]], name: str) -> int | None:
    """Extract a parameter value from params list."""
    for param in params:
        if param.get("name") == name:
            value = param.get("value")
            # Handle array format: value is [123]
            if isinstance(value, list) and len(value) > 0:
                value = value[0]
            if isinstance(value, (int, float)):
                return int(value)
    return None


@dataclass(frozen=True, kw_only=True)
class HomevoltNumberEntityDescription(NumberEntityDescription):
    """Describes a Homevolt number entity."""

    param_key: str


NUMBERS: tuple[HomevoltNumberEntityDescription, ...] = (
    HomevoltNumberEntityDescription(
        key="ecu_main_fuse_size_a",
        translation_key="ecu_main_fuse_size_a",
        param_key="ecu_main_fuse_size_a",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    HomevoltNumberEntityDescription(
        key="ecu_group_fuse_size_a",
        translation_key="ecu_group_fuse_size_a",
        param_key="ecu_group_fuse_size_a",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    # LED strip settings (HMI parameters)
    HomevoltNumberEntityDescription(
        key="ledstrip_bright_max",
        translation_key="ledstrip_bright_max",
        param_key="ledstrip_bright_max",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    HomevoltNumberEntityDescription(
        key="ledstrip_bright_min",
        translation_key="ledstrip_bright_min",
        param_key="ledstrip_bright_min",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    HomevoltNumberEntityDescription(
        key="ledstrip_mode_on_hue",
        translation_key="ledstrip_mode_on_hue",
        param_key="ledstrip_mode_on_hue",
        native_unit_of_measurement="°",
        native_min_value=0,
        native_max_value=360,
        native_step=1,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    HomevoltNumberEntityDescription(
        key="ledstrip_mode_on_saturation",
        translation_key="ledstrip_mode_on_saturation",
        param_key="ledstrip_mode_on_saturation",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomevoltConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homevolt number entities based on a config entry."""
    coordinator = entry.runtime_data

    entities = [HomevoltNumber(coordinator, description) for description in NUMBERS]

    async_add_entities(entities)


class HomevoltNumber(CoordinatorEntity[HomevoltCoordinator], NumberEntity):
    """Representation of a Homevolt number entity."""

    entity_description: HomevoltNumberEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        description: HomevoltNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        self._attr_device_info = get_ecu_device_info(coordinator)

    @property
    def native_value(self) -> int | None:
        """Return the current value."""
        params = self.coordinator.data.get("params", [])
        if not isinstance(params, list):
            return None
        return _get_param_value(params, self.entity_description.param_key)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self.coordinator.api.set_param(self.entity_description.param_key, str(int(value)))
        await self.coordinator.async_request_refresh()
