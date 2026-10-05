"""Button platform for Homevolt Local integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HomevoltConfigEntry
from .coordinator import HomevoltCoordinator
from .device import get_ecu_device_info
from .errors import translate_api_errors

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
            HomevoltSetGridChargeButton(coordinator),
            HomevoltSetGridDischargeButton(coordinator),
            HomevoltSetGridChargeDischargeButton(coordinator),
            HomevoltSetSolarChargeButton(coordinator),
            HomevoltSetFullSolarExportButton(coordinator),
            HomevoltRebootButton(coordinator),
        ]
    )


class HomevoltCommandButton(CoordinatorEntity[HomevoltCoordinator], ButtonEntity):
    """Base for buttons that run one device command.

    Subclasses set `_attr_translation_key` (also used as the unique ID suffix)
    and implement `_async_run_command`. API errors are translated to
    HomeAssistantErrors for every button.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    # The device is unreachable right after a reboot, so there is nothing to refresh.
    _refresh_after_press = True

    def __init__(self, coordinator: HomevoltCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_{self._attr_translation_key}"
        self._attr_device_info = get_ecu_device_info(coordinator)

    async def _async_run_command(self) -> None:
        """Send this button's command to the device."""
        raise NotImplementedError

    async def async_press(self) -> None:
        """Handle button press."""
        with translate_api_errors(self.coordinator.host):
            await self._async_run_command()
        if self._refresh_after_press:
            await self.coordinator.async_request_refresh()


class HomevoltClearScheduleButton(HomevoltCommandButton):
    """Button to clear all scheduled entries on the Homevolt device."""

    _attr_translation_key = "clear_schedule"

    async def _async_run_command(self) -> None:
        """Send the command to clear the schedule."""
        await self.coordinator.api.clear_schedule()


class HomevoltSetIdleButton(HomevoltCommandButton):
    """Button to set the Homevolt battery to idle mode."""

    _attr_translation_key = "set_idle"

    async def _async_run_command(self) -> None:
        """Send the command to set battery to idle mode."""
        await self.coordinator.api.set_idle()


class HomevoltSetChargeButton(HomevoltCommandButton):
    """Button to set the Homevolt battery to charge mode."""

    _attr_translation_key = "set_charge"

    async def _async_run_command(self) -> None:
        """Send the command to set battery to charge mode."""
        await self.coordinator.api.set_charge()


class HomevoltSetDischargeButton(HomevoltCommandButton):
    """Button to set the Homevolt battery to discharge mode."""

    _attr_translation_key = "set_discharge"

    async def _async_run_command(self) -> None:
        """Send the command to set battery to discharge mode."""
        await self.coordinator.api.set_discharge()


class HomevoltSetGridChargeButton(HomevoltCommandButton):
    """Button to set the Homevolt battery to grid charge mode."""

    _attr_translation_key = "set_grid_charge"

    async def _async_run_command(self) -> None:
        """Send the command to set battery to grid charge mode."""
        await self.coordinator.api.set_grid_charge(setpoint=0)


class HomevoltSetGridDischargeButton(HomevoltCommandButton):
    """Button to set the Homevolt battery to grid discharge mode."""

    _attr_translation_key = "set_grid_discharge"

    async def _async_run_command(self) -> None:
        """Send the command to set battery to grid discharge mode."""
        await self.coordinator.api.set_grid_discharge(setpoint=0)


class HomevoltSetGridChargeDischargeButton(HomevoltCommandButton):
    """Button to set the Homevolt battery to grid charge/discharge mode."""

    _attr_translation_key = "set_grid_charge_discharge"

    async def _async_run_command(self) -> None:
        """Send the command to set battery to grid charge/discharge mode."""
        await self.coordinator.api.set_grid_charge_discharge(setpoint=0)


class HomevoltSetSolarChargeButton(HomevoltCommandButton):
    """Button to set the Homevolt battery to solar charge mode."""

    _attr_translation_key = "set_solar_charge"

    async def _async_run_command(self) -> None:
        """Send the command to set battery to solar charge mode."""
        await self.coordinator.api.set_solar_charge()


class HomevoltSetFullSolarExportButton(HomevoltCommandButton):
    """Button to set the Homevolt battery to full solar export mode."""

    _attr_translation_key = "set_full_solar_export"

    async def _async_run_command(self) -> None:
        """Send the command to set battery to full solar export mode."""
        await self.coordinator.api.set_full_solar_export()


class HomevoltRebootButton(HomevoltCommandButton):
    """Button to reboot the Homevolt device via hardware reset."""

    _attr_translation_key = "reboot"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = ButtonDeviceClass.RESTART
    _refresh_after_press = False

    async def _async_run_command(self) -> None:
        """Send the command to reboot the device."""
        await self.coordinator.api.reboot()
