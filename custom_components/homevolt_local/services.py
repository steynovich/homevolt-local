"""Services for Homevolt Local."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .api import HomevoltApi
from .const import DOMAIN
from .coordinator import HomevoltCoordinator
from .errors import translate_api_errors

SERVICE_CLEAR_SCHEDULE = "clear_schedule"
SERVICE_SET_IDLE = "set_idle"
SERVICE_SET_CHARGE = "set_charge"
SERVICE_SET_DISCHARGE = "set_discharge"
SERVICE_SET_GRID_CHARGE = "set_grid_charge"
SERVICE_SET_GRID_DISCHARGE = "set_grid_discharge"
SERVICE_SET_GRID_CHARGE_DISCHARGE = "set_grid_charge_discharge"
SERVICE_SET_SOLAR_CHARGE = "set_solar_charge"
SERVICE_SET_SOLAR_CHARGE_DISCHARGE = "set_solar_charge_discharge"
SERVICE_SET_FULL_SOLAR_EXPORT = "set_full_solar_export"
SERVICE_REBOOT = "reboot"
SERVICE_SET_SCHEDULE = "set_schedule"

_DEVICE_ID: dict[Any, Any] = {vol.Required("device_id"): cv.string}
_SETPOINT: dict[Any, Any] = {vol.Optional("setpoint"): vol.All(vol.Coerce(int), vol.Range(min=0))}
_SPLIT_SETPOINTS: dict[Any, Any] = {
    vol.Optional("charge_setpoint"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    vol.Optional("discharge_setpoint"): vol.All(vol.Coerce(int), vol.Range(min=0)),
}
_SOC_LIMITS: dict[Any, Any] = {
    vol.Optional("min_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    vol.Optional("max_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
}

SERVICE_REBOOT_SCHEMA = vol.Schema(_DEVICE_ID)
SERVICE_CLEAR_SCHEDULE_SCHEMA = vol.Schema(_DEVICE_ID)
SERVICE_SET_IDLE_SCHEMA = vol.Schema(
    {**_DEVICE_ID, vol.Optional("offline", default=False): cv.boolean}
)
# Shared by every service that takes only a setpoint and SOC limits.
_SETPOINT_SOC_SCHEMA = vol.Schema({**_DEVICE_ID, **_SETPOINT, **_SOC_LIMITS})
SERVICE_SET_GRID_CHARGE_DISCHARGE_SCHEMA = vol.Schema(
    {
        **_DEVICE_ID,
        vol.Required("setpoint"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        **_SPLIT_SETPOINTS,
        **_SOC_LIMITS,
    }
)
SERVICE_SET_SOLAR_CHARGE_DISCHARGE_SCHEMA = vol.Schema(
    {**_DEVICE_ID, **_SETPOINT, **_SPLIT_SETPOINTS, **_SOC_LIMITS}
)

# ISO 8601 datetime pattern (YYYY-MM-DDTHH:mm:ss)
ISO8601_DATETIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")


def validate_iso8601_datetime(value: str) -> str:
    """Validate ISO 8601 datetime string to prevent command injection."""
    if not isinstance(value, str):
        raise vol.Invalid(f"Expected string, got {type(value).__name__}")
    if not ISO8601_DATETIME_PATTERN.match(value):
        raise vol.Invalid(f"Invalid datetime format: {value}. Expected YYYY-MM-DDTHH:mm:ss")
    return value


SCHEDULE_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required("type"): vol.All(vol.Coerce(int), vol.Range(min=0, max=9)),
        vol.Optional("from_time"): validate_iso8601_datetime,
        vol.Optional("to_time"): validate_iso8601_datetime,
        vol.Optional("min_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("max_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("setpoint"): vol.All(vol.Coerce(int), vol.Range(min=-25000, max=25000)),
        vol.Optional("max_charge"): vol.All(vol.Coerce(int), vol.Range(min=0, max=25000)),
        vol.Optional("max_discharge"): vol.All(vol.Coerce(int), vol.Range(min=0, max=25000)),
        vol.Optional("import_limit"): vol.All(vol.Coerce(int), vol.Range(min=-25000, max=25000)),
        vol.Optional("export_limit"): vol.All(vol.Coerce(int), vol.Range(min=-25000, max=25000)),
    }
)

SERVICE_SET_SCHEDULE_SCHEMA = vol.Schema(
    {
        **_DEVICE_ID,
        vol.Required("schedule"): vol.All(
            cv.ensure_list, vol.Length(min=1, max=100), [SCHEDULE_ENTRY_SCHEMA]
        ),
    }
)

type _Command = Callable[[HomevoltApi, dict[str, Any]], Awaitable[Any]]


@dataclass(frozen=True, kw_only=True)
class _ServiceSpec:
    """How to validate and run one service."""

    schema: vol.Schema
    command: _Command
    # The device is unreachable right after a reboot, so there is nothing to refresh.
    refresh: bool = True


def _setpoint_soc(data: dict[str, Any]) -> dict[str, Any]:
    """Pick the setpoint/SOC keyword arguments from service data."""
    return {k: data.get(k) for k in ("setpoint", "min_soc", "max_soc")}


def _split_setpoints(data: dict[str, Any]) -> dict[str, Any]:
    """Pick the split charge/discharge keyword arguments from service data."""
    keys = ("setpoint", "charge_setpoint", "discharge_setpoint", "min_soc", "max_soc")
    return {k: data.get(k) for k in keys}


SERVICES: dict[str, _ServiceSpec] = {
    SERVICE_CLEAR_SCHEDULE: _ServiceSpec(
        schema=SERVICE_CLEAR_SCHEDULE_SCHEMA, command=lambda api, data: api.clear_schedule()
    ),
    SERVICE_SET_IDLE: _ServiceSpec(
        schema=SERVICE_SET_IDLE_SCHEMA,
        command=lambda api, data: api.set_idle(data.get("offline", False)),
    ),
    SERVICE_SET_CHARGE: _ServiceSpec(
        schema=_SETPOINT_SOC_SCHEMA,
        command=lambda api, data: api.set_charge(**_setpoint_soc(data)),
    ),
    SERVICE_SET_DISCHARGE: _ServiceSpec(
        schema=_SETPOINT_SOC_SCHEMA,
        command=lambda api, data: api.set_discharge(**_setpoint_soc(data)),
    ),
    SERVICE_SET_GRID_CHARGE: _ServiceSpec(
        schema=_SETPOINT_SOC_SCHEMA,
        command=lambda api, data: api.set_grid_charge(**_setpoint_soc(data)),
    ),
    SERVICE_SET_GRID_DISCHARGE: _ServiceSpec(
        schema=_SETPOINT_SOC_SCHEMA,
        command=lambda api, data: api.set_grid_discharge(**_setpoint_soc(data)),
    ),
    SERVICE_SET_GRID_CHARGE_DISCHARGE: _ServiceSpec(
        schema=SERVICE_SET_GRID_CHARGE_DISCHARGE_SCHEMA,
        command=lambda api, data: api.set_grid_charge_discharge(**_split_setpoints(data)),
    ),
    SERVICE_SET_SOLAR_CHARGE: _ServiceSpec(
        schema=_SETPOINT_SOC_SCHEMA,
        command=lambda api, data: api.set_solar_charge(**_setpoint_soc(data)),
    ),
    SERVICE_SET_SOLAR_CHARGE_DISCHARGE: _ServiceSpec(
        schema=SERVICE_SET_SOLAR_CHARGE_DISCHARGE_SCHEMA,
        command=lambda api, data: api.set_solar_charge_discharge(**_split_setpoints(data)),
    ),
    SERVICE_SET_FULL_SOLAR_EXPORT: _ServiceSpec(
        schema=_SETPOINT_SOC_SCHEMA,
        command=lambda api, data: api.set_full_solar_export(**_setpoint_soc(data)),
    ),
    SERVICE_SET_SCHEDULE: _ServiceSpec(
        schema=SERVICE_SET_SCHEDULE_SCHEMA,
        command=lambda api, data: api.set_schedule(data["schedule"]),
    ),
    SERVICE_REBOOT: _ServiceSpec(
        schema=SERVICE_REBOOT_SCHEMA, command=lambda api, data: api.reboot(), refresh=False
    ),
}


def _async_get_coordinator(hass: HomeAssistant, device_id: str) -> HomevoltCoordinator:
    """Resolve the coordinator for a device, raising if it can't be found."""
    device_entry = dr.async_get(hass).async_get(device_id)
    if device_entry is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"device_id": device_id},
        )
    for config_entry_id in device_entry.config_entries:
        config_entry = hass.config_entries.async_get_entry(config_entry_id)
        if config_entry and config_entry.domain == DOMAIN:
            return cast(HomevoltCoordinator, config_entry.runtime_data)
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="config_entry_not_found",
        translation_placeholders={"device_id": device_id},
    )


def _make_handler(hass: HomeAssistant, spec: _ServiceSpec) -> Callable[[ServiceCall], Any]:
    """Create the service handler for a spec."""

    async def handler(call: ServiceCall) -> None:
        coordinator = _async_get_coordinator(hass, call.data["device_id"])
        with translate_api_errors(coordinator.host):
            await spec.command(coordinator.api, call.data)
        if spec.refresh:
            await coordinator.async_request_refresh()

    return handler


def async_setup_services(hass: HomeAssistant) -> None:
    """Register all services that aren't registered yet."""
    for name, spec in SERVICES.items():
        if not hass.services.has_service(DOMAIN, name):
            hass.services.async_register(
                DOMAIN, name, _make_handler(hass, spec), schema=spec.schema
            )


def async_unload_services(hass: HomeAssistant) -> None:
    """Remove all services."""
    for name in SERVICES:
        hass.services.async_remove(DOMAIN, name)
