"""Config flow for Homevolt Local integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import HomevoltApi, HomevoltAuthError, HomevoltConnectionError, HomevoltRateLimitError
from .const import DOMAIN
from .coordinator import _extract_device_id_from_host, _extract_ecu_id

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


class HomevoltConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homevolt Local."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str | None = None
        self._device_id: str | None = None
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            username = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)

            api = HomevoltApi(host, password, username)

            try:
                await api.test_connection()
                # Also fetch EMS to get ecu_id for device identification
                ems_data = await api.get_ems()
            except HomevoltAuthError:
                errors["base"] = "invalid_auth"
            except HomevoltRateLimitError:
                errors["base"] = "rate_limited"
            except HomevoltConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Extract device identifier (prefer ecu_id from EMS, fallback to hostname)
                device_id = _extract_ecu_id(ems_data) or _extract_device_id_from_host(host) or host

                # Use device ID as unique ID to prevent duplicate entries for same device
                device_id = str(device_id)
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()

                title = f"Homevolt {device_id}"

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_HOST: host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )
            finally:
                await api.close()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauthentication request."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        self._host = entry_data[CONF_HOST]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}

        assert self._host is not None
        assert self._reauth_entry is not None

        if user_input is not None:
            username = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)

            api = HomevoltApi(self._host, password, username)

            try:
                await api.test_connection()
            except HomevoltAuthError:
                errors["base"] = "invalid_auth"
            except HomevoltRateLimitError:
                errors["base"] = "rate_limited"
            except HomevoltConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={
                        **self._reauth_entry.data,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            finally:
                await api.close()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={"host": self._host},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration flow."""
        reconfigure_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert reconfigure_entry is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            username = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)

            api = HomevoltApi(host, password, username)

            try:
                await api.test_connection()
                ems_data = await api.get_ems()
            except HomevoltAuthError:
                errors["base"] = "invalid_auth"
            except HomevoltRateLimitError:
                errors["base"] = "rate_limited"
            except HomevoltConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during reconfigure")
                errors["base"] = "unknown"
            else:
                # Verify it's the same device
                device_id = str(
                    _extract_ecu_id(ems_data) or _extract_device_id_from_host(host) or host
                )
                if reconfigure_entry.unique_id and device_id != reconfigure_entry.unique_id:
                    return self.async_abort(reason="different_device")

                self.hass.config_entries.async_update_entry(
                    reconfigure_entry,
                    data={
                        CONF_HOST: host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )
                await self.hass.config_entries.async_reload(reconfigure_entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")
            finally:
                await api.close()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=reconfigure_entry.data.get(CONF_HOST)): str,
                    vol.Optional(
                        CONF_USERNAME, default=reconfigure_entry.data.get(CONF_USERNAME)
                    ): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        host = str(discovery_info.ip_address)
        name = discovery_info.name

        _LOGGER.debug("Zeroconf discovery: %s at %s", name, host)

        # Extract device ID from mDNS name (e.g., "homevolt-abc123._http._tcp.local.")
        device_id = _extract_device_id_from_host(name) or host

        # Set unique ID to prevent duplicate discoveries
        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._host = host
        self._device_id = device_id

        # Set title for discovery UI
        self.context["title_placeholders"] = {"name": f"Homevolt {device_id}"}

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery confirmation."""
        errors: dict[str, str] = {}

        assert self._host is not None

        if user_input is not None:
            username = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)

            api = HomevoltApi(self._host, password, username)

            try:
                await api.test_connection()
                ems_data = await api.get_ems()
            except HomevoltAuthError:
                errors["base"] = "invalid_auth"
            except HomevoltRateLimitError:
                errors["base"] = "rate_limited"
            except HomevoltConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during zeroconf setup")
                errors["base"] = "unknown"
            else:
                # Update device ID with ecu_id if available
                ecu_id = _extract_ecu_id(ems_data)
                if ecu_id:
                    await self.async_set_unique_id(str(ecu_id))
                    self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})
                    self._device_id = str(ecu_id)

                title = f"Homevolt {self._device_id}"

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_HOST: self._host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )
            finally:
                await api.close()

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={"host": self._host},
        )
