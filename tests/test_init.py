"""Tests for Homevolt Local integration setup."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components.homevolt_local.api import (
    HomevoltAuthError,
    HomevoltConnectionError,
    HomevoltRateLimitError,
)
from custom_components.homevolt_local.const import DOMAIN


async def test_setup_entry_auth_error(
    hass: HomeAssistant,
    mock_config_data: dict,
) -> None:
    """Test setup fails with auth error."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.homevolt_local import async_setup_entry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        unique_id="test123",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.homevolt_local.HomevoltApi",
        autospec=True,
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.test_connection = AsyncMock(side_effect=HomevoltAuthError("Invalid credentials"))

        with pytest.raises(ConfigEntryAuthFailed):
            await async_setup_entry(hass, entry)


async def test_setup_entry_rate_limit_error(
    hass: HomeAssistant,
    mock_config_data: dict,
) -> None:
    """Test setup fails with rate limit error."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.homevolt_local import async_setup_entry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        unique_id="test123",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.homevolt_local.HomevoltApi",
        autospec=True,
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.test_connection = AsyncMock(side_effect=HomevoltRateLimitError("Rate limited"))

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_data: dict,
) -> None:
    """Test setup fails with connection error."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.homevolt_local import async_setup_entry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        unique_id="test123",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.homevolt_local.HomevoltApi",
        autospec=True,
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.test_connection = AsyncMock(
            side_effect=HomevoltConnectionError("Connection failed")
        )

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)
