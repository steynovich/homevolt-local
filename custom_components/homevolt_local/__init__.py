"""The Homevolt Local integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    HomevoltApi,
    HomevoltAuthError,
    HomevoltConnectionError,
    HomevoltNotLocalModeError,
    HomevoltRateLimitError,
)
from .const import DOMAIN
from .coordinator import HomevoltCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

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

SERVICE_CLEAR_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
    }
)

SERVICE_SET_IDLE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Optional("offline", default=False): cv.boolean,
    }
)

SERVICE_SET_CHARGE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Optional("setpoint"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("min_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("max_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }
)

SERVICE_SET_DISCHARGE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Optional("setpoint"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("min_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("max_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }
)

SERVICE_SET_GRID_CHARGE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Optional("setpoint"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("min_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("max_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }
)

SERVICE_SET_GRID_DISCHARGE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Optional("setpoint"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("min_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("max_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }
)

SERVICE_SET_GRID_CHARGE_DISCHARGE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Required("setpoint"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("charge_setpoint"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("discharge_setpoint"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("min_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("max_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }
)

SERVICE_SET_SOLAR_CHARGE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Optional("setpoint"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("min_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("max_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }
)

SERVICE_SET_SOLAR_CHARGE_DISCHARGE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Optional("setpoint"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("charge_setpoint"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("discharge_setpoint"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("min_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("max_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }
)

SERVICE_SET_FULL_SOLAR_EXPORT_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Optional("setpoint"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("min_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("max_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }
)

type HomevoltConfigEntry = ConfigEntry[HomevoltCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: HomevoltConfigEntry) -> bool:
    """Set up Homevolt Local from a config entry."""
    host = entry.data[CONF_HOST]
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    session = async_get_clientsession(hass)
    api = HomevoltApi(host, password, username, session)

    try:
        # Test connection first
        await api.test_connection()
        # Fetch initial data including EMS for device identification
        initial_data = await api.get_all_data()
    except HomevoltAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
            translation_placeholders={"host": host},
        ) from err
    except HomevoltRateLimitError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="rate_limited",
        ) from err
    except HomevoltConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": host},
        ) from err

    coordinator = HomevoltCoordinator(hass, api, host, initial_data)
    coordinator.config_entry = entry

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services if not already registered
    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR_SCHEDULE):

        async def async_clear_schedule(call: ServiceCall) -> None:
            """Handle the clear_schedule service call."""
            device_id = call.data["device_id"]
            device_registry = dr.async_get(hass)
            device_entry = device_registry.async_get(device_id)

            if device_entry is None:
                _LOGGER.error("Device %s not found", device_id)
                return

            # Find the config entry for this device
            for config_entry_id in device_entry.config_entries:
                config_entry = hass.config_entries.async_get_entry(config_entry_id)
                if config_entry and config_entry.domain == DOMAIN:
                    coord: HomevoltCoordinator = config_entry.runtime_data
                    await coord.api.clear_schedule()
                    await coord.async_request_refresh()
                    return

            _LOGGER.error("No Homevolt config entry found for device %s", device_id)

        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_SCHEDULE,
            async_clear_schedule,
            schema=SERVICE_CLEAR_SCHEDULE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_IDLE):

        async def async_set_idle(call: ServiceCall) -> None:
            """Handle the set_idle service call."""
            device_id = call.data["device_id"]
            offline = call.data.get("offline", False)
            device_registry = dr.async_get(hass)
            device_entry = device_registry.async_get(device_id)

            if device_entry is None:
                _LOGGER.error("Device %s not found", device_id)
                return

            # Find the config entry for this device
            for config_entry_id in device_entry.config_entries:
                config_entry = hass.config_entries.async_get_entry(config_entry_id)
                if config_entry and config_entry.domain == DOMAIN:
                    coord: HomevoltCoordinator = config_entry.runtime_data
                    try:
                        await coord.api.set_idle(offline)
                        await coord.async_request_refresh()
                    except HomevoltNotLocalModeError as err:
                        raise HomeAssistantError(
                            translation_domain=DOMAIN,
                            translation_key="not_local_mode",
                        ) from err
                    return

            _LOGGER.error("No Homevolt config entry found for device %s", device_id)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_IDLE,
            async_set_idle,
            schema=SERVICE_SET_IDLE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_CHARGE):

        async def async_set_charge(call: ServiceCall) -> None:
            """Handle the set_charge service call."""
            device_id = call.data["device_id"]
            setpoint = call.data.get("setpoint")
            min_soc = call.data.get("min_soc")
            max_soc = call.data.get("max_soc")
            device_registry = dr.async_get(hass)
            device_entry = device_registry.async_get(device_id)

            if device_entry is None:
                _LOGGER.error("Device %s not found", device_id)
                return

            # Find the config entry for this device
            for config_entry_id in device_entry.config_entries:
                config_entry = hass.config_entries.async_get_entry(config_entry_id)
                if config_entry and config_entry.domain == DOMAIN:
                    coord: HomevoltCoordinator = config_entry.runtime_data
                    try:
                        await coord.api.set_charge(setpoint, min_soc, max_soc)
                        await coord.async_request_refresh()
                    except HomevoltNotLocalModeError as err:
                        raise HomeAssistantError(
                            translation_domain=DOMAIN,
                            translation_key="not_local_mode",
                        ) from err
                    return

            _LOGGER.error("No Homevolt config entry found for device %s", device_id)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_CHARGE,
            async_set_charge,
            schema=SERVICE_SET_CHARGE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_DISCHARGE):

        async def async_set_discharge(call: ServiceCall) -> None:
            """Handle the set_discharge service call."""
            device_id = call.data["device_id"]
            setpoint = call.data.get("setpoint")
            min_soc = call.data.get("min_soc")
            max_soc = call.data.get("max_soc")
            device_registry = dr.async_get(hass)
            device_entry = device_registry.async_get(device_id)

            if device_entry is None:
                _LOGGER.error("Device %s not found", device_id)
                return

            # Find the config entry for this device
            for config_entry_id in device_entry.config_entries:
                config_entry = hass.config_entries.async_get_entry(config_entry_id)
                if config_entry and config_entry.domain == DOMAIN:
                    coord: HomevoltCoordinator = config_entry.runtime_data
                    try:
                        await coord.api.set_discharge(setpoint, min_soc, max_soc)
                        await coord.async_request_refresh()
                    except HomevoltNotLocalModeError as err:
                        raise HomeAssistantError(
                            translation_domain=DOMAIN,
                            translation_key="not_local_mode",
                        ) from err
                    return

            _LOGGER.error("No Homevolt config entry found for device %s", device_id)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_DISCHARGE,
            async_set_discharge,
            schema=SERVICE_SET_DISCHARGE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_GRID_CHARGE):

        async def async_set_grid_charge(call: ServiceCall) -> None:
            """Handle the set_grid_charge service call."""
            device_id = call.data["device_id"]
            setpoint = call.data.get("setpoint")
            min_soc = call.data.get("min_soc")
            max_soc = call.data.get("max_soc")
            device_registry = dr.async_get(hass)
            device_entry = device_registry.async_get(device_id)

            if device_entry is None:
                _LOGGER.error("Device %s not found", device_id)
                return

            # Find the config entry for this device
            for config_entry_id in device_entry.config_entries:
                config_entry = hass.config_entries.async_get_entry(config_entry_id)
                if config_entry and config_entry.domain == DOMAIN:
                    coord: HomevoltCoordinator = config_entry.runtime_data
                    try:
                        await coord.api.set_grid_charge(setpoint, min_soc, max_soc)
                        await coord.async_request_refresh()
                    except HomevoltNotLocalModeError as err:
                        raise HomeAssistantError(
                            translation_domain=DOMAIN,
                            translation_key="not_local_mode",
                        ) from err
                    return

            _LOGGER.error("No Homevolt config entry found for device %s", device_id)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_GRID_CHARGE,
            async_set_grid_charge,
            schema=SERVICE_SET_GRID_CHARGE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_GRID_DISCHARGE):

        async def async_set_grid_discharge(call: ServiceCall) -> None:
            """Handle the set_grid_discharge service call."""
            device_id = call.data["device_id"]
            setpoint = call.data.get("setpoint")
            min_soc = call.data.get("min_soc")
            max_soc = call.data.get("max_soc")
            device_registry = dr.async_get(hass)
            device_entry = device_registry.async_get(device_id)

            if device_entry is None:
                _LOGGER.error("Device %s not found", device_id)
                return

            # Find the config entry for this device
            for config_entry_id in device_entry.config_entries:
                config_entry = hass.config_entries.async_get_entry(config_entry_id)
                if config_entry and config_entry.domain == DOMAIN:
                    coord: HomevoltCoordinator = config_entry.runtime_data
                    try:
                        await coord.api.set_grid_discharge(setpoint, min_soc, max_soc)
                        await coord.async_request_refresh()
                    except HomevoltNotLocalModeError as err:
                        raise HomeAssistantError(
                            translation_domain=DOMAIN,
                            translation_key="not_local_mode",
                        ) from err
                    return

            _LOGGER.error("No Homevolt config entry found for device %s", device_id)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_GRID_DISCHARGE,
            async_set_grid_discharge,
            schema=SERVICE_SET_GRID_DISCHARGE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_GRID_CHARGE_DISCHARGE):

        async def async_set_grid_charge_discharge(call: ServiceCall) -> None:
            """Handle the set_grid_charge_discharge service call."""
            device_id = call.data["device_id"]
            setpoint = call.data["setpoint"]
            charge_setpoint = call.data.get("charge_setpoint")
            discharge_setpoint = call.data.get("discharge_setpoint")
            min_soc = call.data.get("min_soc")
            max_soc = call.data.get("max_soc")
            device_registry = dr.async_get(hass)
            device_entry = device_registry.async_get(device_id)

            if device_entry is None:
                _LOGGER.error("Device %s not found", device_id)
                return

            # Find the config entry for this device
            for config_entry_id in device_entry.config_entries:
                config_entry = hass.config_entries.async_get_entry(config_entry_id)
                if config_entry and config_entry.domain == DOMAIN:
                    coord: HomevoltCoordinator = config_entry.runtime_data
                    try:
                        await coord.api.set_grid_charge_discharge(
                            setpoint, charge_setpoint, discharge_setpoint, min_soc, max_soc
                        )
                        await coord.async_request_refresh()
                    except HomevoltNotLocalModeError as err:
                        raise HomeAssistantError(
                            translation_domain=DOMAIN,
                            translation_key="not_local_mode",
                        ) from err
                    return

            _LOGGER.error("No Homevolt config entry found for device %s", device_id)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_GRID_CHARGE_DISCHARGE,
            async_set_grid_charge_discharge,
            schema=SERVICE_SET_GRID_CHARGE_DISCHARGE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_SOLAR_CHARGE):

        async def async_set_solar_charge(call: ServiceCall) -> None:
            """Handle the set_solar_charge service call."""
            device_id = call.data["device_id"]
            setpoint = call.data.get("setpoint")
            min_soc = call.data.get("min_soc")
            max_soc = call.data.get("max_soc")
            device_registry = dr.async_get(hass)
            device_entry = device_registry.async_get(device_id)

            if device_entry is None:
                _LOGGER.error("Device %s not found", device_id)
                return

            # Find the config entry for this device
            for config_entry_id in device_entry.config_entries:
                config_entry = hass.config_entries.async_get_entry(config_entry_id)
                if config_entry and config_entry.domain == DOMAIN:
                    coord: HomevoltCoordinator = config_entry.runtime_data
                    try:
                        await coord.api.set_solar_charge(setpoint, min_soc, max_soc)
                        await coord.async_request_refresh()
                    except HomevoltNotLocalModeError as err:
                        raise HomeAssistantError(
                            translation_domain=DOMAIN,
                            translation_key="not_local_mode",
                        ) from err
                    return

            _LOGGER.error("No Homevolt config entry found for device %s", device_id)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_SOLAR_CHARGE,
            async_set_solar_charge,
            schema=SERVICE_SET_SOLAR_CHARGE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_SOLAR_CHARGE_DISCHARGE):

        async def async_set_solar_charge_discharge(call: ServiceCall) -> None:
            """Handle the set_solar_charge_discharge service call."""
            device_id = call.data["device_id"]
            setpoint = call.data.get("setpoint")
            charge_setpoint = call.data.get("charge_setpoint")
            discharge_setpoint = call.data.get("discharge_setpoint")
            min_soc = call.data.get("min_soc")
            max_soc = call.data.get("max_soc")
            device_registry = dr.async_get(hass)
            device_entry = device_registry.async_get(device_id)

            if device_entry is None:
                _LOGGER.error("Device %s not found", device_id)
                return

            # Find the config entry for this device
            for config_entry_id in device_entry.config_entries:
                config_entry = hass.config_entries.async_get_entry(config_entry_id)
                if config_entry and config_entry.domain == DOMAIN:
                    coord: HomevoltCoordinator = config_entry.runtime_data
                    try:
                        await coord.api.set_solar_charge_discharge(
                            setpoint, charge_setpoint, discharge_setpoint, min_soc, max_soc
                        )
                        await coord.async_request_refresh()
                    except HomevoltNotLocalModeError as err:
                        raise HomeAssistantError(
                            translation_domain=DOMAIN,
                            translation_key="not_local_mode",
                        ) from err
                    return

            _LOGGER.error("No Homevolt config entry found for device %s", device_id)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_SOLAR_CHARGE_DISCHARGE,
            async_set_solar_charge_discharge,
            schema=SERVICE_SET_SOLAR_CHARGE_DISCHARGE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_FULL_SOLAR_EXPORT):

        async def async_set_full_solar_export(call: ServiceCall) -> None:
            """Handle the set_full_solar_export service call."""
            device_id = call.data["device_id"]
            setpoint = call.data.get("setpoint")
            min_soc = call.data.get("min_soc")
            max_soc = call.data.get("max_soc")
            device_registry = dr.async_get(hass)
            device_entry = device_registry.async_get(device_id)

            if device_entry is None:
                _LOGGER.error("Device %s not found", device_id)
                return

            # Find the config entry for this device
            for config_entry_id in device_entry.config_entries:
                config_entry = hass.config_entries.async_get_entry(config_entry_id)
                if config_entry and config_entry.domain == DOMAIN:
                    coord: HomevoltCoordinator = config_entry.runtime_data
                    try:
                        await coord.api.set_full_solar_export(setpoint, min_soc, max_soc)
                        await coord.async_request_refresh()
                    except HomevoltNotLocalModeError as err:
                        raise HomeAssistantError(
                            translation_domain=DOMAIN,
                            translation_key="not_local_mode",
                        ) from err
                    return

            _LOGGER.error("No Homevolt config entry found for device %s", device_id)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_FULL_SOLAR_EXPORT,
            async_set_full_solar_export,
            schema=SERVICE_SET_FULL_SOLAR_EXPORT_SCHEMA,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HomevoltConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
