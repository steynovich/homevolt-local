"""Button platform for Homevolt Local integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomevoltConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homevolt buttons based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            HomevoltClearScheduleButton(coordinator),
            HomevoltSetIdleButton(coordinator),
            HomevoltSetChargeButton(coordinator),
            HomevoltSetDischargeButton(coordinator),
            HomevoltSetSolarChargeButton(coordinator),
            HomevoltSetFullSolarExportButton(coordinator),
            HomevoltRebootButton(coordinator),
        ]
    )


class HomevoltClearScheduleButton(CoordinatorEntity[HomevoltCoordinator], ButtonEntity):
    """Button to clear all scheduled entries on the Homevolt device."""

    _attr_has_entity_name = True
    _attr_translation_key = "clear_schedule"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: HomevoltCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_clear_schedule"
        self._attr_device_info = get_ecu_device_info(coordinator)

    async def async_press(self) -> None:
        """Handle button press to clear the schedule."""
        await self.coordinator.api.clear_schedule()
        await self.coordinator.async_request_refresh()


class HomevoltSetIdleButton(CoordinatorEntity[HomevoltCoordinator], ButtonEntity):
    """Button to set the Homevolt battery to idle mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "set_idle"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: HomevoltCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_set_idle"
        self._attr_device_info = get_ecu_device_info(coordinator)

    async def async_press(self) -> None:
        """Handle button press to set battery to idle mode."""
        await self.coordinator.api.set_idle()
        await self.coordinator.async_request_refresh()


class HomevoltSetChargeButton(CoordinatorEntity[HomevoltCoordinator], ButtonEntity):
    """Button to set the Homevolt battery to charge mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "set_charge"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: HomevoltCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_set_charge"
        self._attr_device_info = get_ecu_device_info(coordinator)

    async def async_press(self) -> None:
        """Handle button press to set battery to charge mode."""
        await self.coordinator.api.set_charge()
        await self.coordinator.async_request_refresh()


class HomevoltSetDischargeButton(CoordinatorEntity[HomevoltCoordinator], ButtonEntity):
    """Button to set the Homevolt battery to discharge mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "set_discharge"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: HomevoltCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_set_discharge"
        self._attr_device_info = get_ecu_device_info(coordinator)

    async def async_press(self) -> None:
        """Handle button press to set battery to discharge mode."""
        await self.coordinator.api.set_discharge()
        await self.coordinator.async_request_refresh()


class HomevoltSetSolarChargeButton(CoordinatorEntity[HomevoltCoordinator], ButtonEntity):
    """Button to set the Homevolt battery to solar charge mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "set_solar_charge"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: HomevoltCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_set_solar_charge"
        self._attr_device_info = get_ecu_device_info(coordinator)

    async def async_press(self) -> None:
        """Handle button press to set battery to solar charge mode."""
        await self.coordinator.api.set_solar_charge()
        await self.coordinator.async_request_refresh()


class HomevoltSetFullSolarExportButton(CoordinatorEntity[HomevoltCoordinator], ButtonEntity):
    """Button to set the Homevolt battery to full solar export mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "set_full_solar_export"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: HomevoltCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_set_full_solar_export"
        self._attr_device_info = get_ecu_device_info(coordinator)

    async def async_press(self) -> None:
        """Handle button press to set battery to full solar export mode."""
        await self.coordinator.api.set_full_solar_export()
        await self.coordinator.async_request_refresh()


class HomevoltRebootButton(CoordinatorEntity[HomevoltCoordinator], ButtonEntity):
    """Button to reboot the Homevolt device via hardware reset."""

    _attr_has_entity_name = True
    _attr_translation_key = "reboot"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(self, coordinator: HomevoltCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_reboot"
        self._attr_device_info = get_ecu_device_info(coordinator)

    async def async_press(self) -> None:
        """Handle button press to reboot the device."""
        await self.coordinator.api.reboot()
