"""The Homevolt Local integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    HomevoltApi,
    HomevoltAuthError,
    HomevoltConnectionError,
    HomevoltRateLimitError,
)
from .const import DOMAIN
from .coordinator import HomevoltCoordinator
from .device import async_register_ecu_device
from .services import async_setup_services, async_unload_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

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

    # Register the ECU device up front so the cluster device can reference it by
    # device registry entry id (via_device_id) when the platforms are set up.
    coordinator.ecu_device_entry_id = async_register_ecu_device(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HomevoltConfigEntry) -> bool:
    """Unload a config entry."""
    result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if result:
        # Remove services if no more entries remain
        remaining = [
            e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id != entry.entry_id
        ]
        if not remaining:
            async_unload_services(hass)
    return result
