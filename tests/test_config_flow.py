"""Tests for Homevolt Local config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from custom_components.homevolt_local.const import DOMAIN


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}


async def test_form_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_homevolt_api: AsyncMock,
) -> None:
    """Test successful form submission."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "homevolt-test.local",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "testpass",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Homevolt test123"
    assert result["data"] == {
        CONF_HOST: "homevolt-test.local",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "testpass",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_success_no_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_homevolt_api: AsyncMock,
) -> None:
    """Test successful form submission without authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "homevolt-test.local",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "homevolt-test.local"
    assert result["data"].get(CONF_USERNAME) is None
    assert result["data"].get(CONF_PASSWORD) is None


async def test_form_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test form with invalid authentication."""
    from custom_components.homevolt_local.api import HomevoltAuthError

    with patch(
        "custom_components.homevolt_local.config_flow.HomevoltApi",
        autospec=True,
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.test_connection = AsyncMock(side_effect=HomevoltAuthError("Invalid credentials"))
        mock_api.close = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "homevolt-test.local",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "wrongpass",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}


async def test_form_rate_limited(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test form when rate limited due to too many auth failures."""
    from custom_components.homevolt_local.api import HomevoltRateLimitError

    with patch(
        "custom_components.homevolt_local.config_flow.HomevoltApi",
        autospec=True,
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.test_connection = AsyncMock(side_effect=HomevoltRateLimitError("Rate limited"))
        mock_api.close = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "homevolt-test.local",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "wrongpass",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "rate_limited"}


async def test_form_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test form when cannot connect."""
    from custom_components.homevolt_local.api import HomevoltConnectionError

    with patch(
        "custom_components.homevolt_local.config_flow.HomevoltApi",
        autospec=True,
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.test_connection = AsyncMock(
            side_effect=HomevoltConnectionError("Connection failed")
        )
        mock_api.close = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "homevolt-test.local",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test form with unknown error."""
    with patch(
        "custom_components.homevolt_local.config_flow.HomevoltApi",
        autospec=True,
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.test_connection = AsyncMock(side_effect=Exception("Unknown error"))
        mock_api.close = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "homevolt-test.local",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_homevolt_api: AsyncMock,
) -> None:
    """Test form when device is already configured."""
    # Create first entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "homevolt-test.local",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Try to add same device again
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "homevolt-test.local",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# Reauthentication tests


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_homevolt_api: AsyncMock,
) -> None:
    """Test reauthentication flow."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    # Create initial entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "homevolt-test.local",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "oldpass",
        },
        unique_id="test123",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "newpass",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauthentication flow with invalid auth."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.homevolt_local.api import HomevoltAuthError

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "homevolt-test.local",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "oldpass",
        },
        unique_id="test123",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.homevolt_local.config_flow.HomevoltApi",
        autospec=True,
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.test_connection = AsyncMock(side_effect=HomevoltAuthError("Invalid credentials"))
        mock_api.close = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "wrongpass",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}


# Reconfiguration tests


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_homevolt_api: AsyncMock,
) -> None:
    """Test reconfiguration flow."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "homevolt-old.local",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "testpass",
        },
        unique_id="test123",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "homevolt-new.local",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "newpass",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_flow_different_device(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfiguration flow aborts when device is different."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "homevolt-old.local",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "testpass",
        },
        unique_id="original_device",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.homevolt_local.config_flow.HomevoltApi",
        autospec=True,
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.test_connection = AsyncMock(return_value={"status": "ok"})
        mock_api.get_ems = AsyncMock(return_value={"ems": [{"ecu_id": "different_device"}]})
        mock_api.close = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "homevolt-new.local",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "testpass",
            },
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "different_device"


# Zeroconf discovery tests


async def test_zeroconf_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_homevolt_api: AsyncMock,
) -> None:
    """Test Zeroconf discovery flow."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="homevolt-abc123.local.",
        name="homevolt-abc123._http._tcp.local.",
        port=80,
        properties={},
        type="_http._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},  # No auth needed
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "test123" in result["title"]  # Uses ecu_id from mock


async def test_zeroconf_discovery_with_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test Zeroconf discovery flow with authentication."""
    from custom_components.homevolt_local.api import HomevoltAuthError

    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="homevolt-abc123.local.",
        name="homevolt-abc123._http._tcp.local.",
        port=80,
        properties={},
        type="_http._tcp.local.",
    )

    with patch(
        "custom_components.homevolt_local.config_flow.HomevoltApi",
        autospec=True,
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        # First call fails (no auth), second succeeds (with auth)
        mock_api.test_connection = AsyncMock(
            side_effect=[
                HomevoltAuthError("Auth required"),
                {"status": "ok"},
            ]
        )
        mock_api.get_ems = AsyncMock(return_value={"ems": [{"ecu_id": "abc123"}]})
        mock_api.close = AsyncMock()

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )

        # First attempt without auth fails
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

        # Second attempt with auth succeeds
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "secret",
            },
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_discovery_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_homevolt_api: AsyncMock,
) -> None:
    """Test Zeroconf discovery aborts when already configured."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    # Create existing entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.50",
        },
        unique_id="abc123",
    )
    entry.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),  # Different IP, same device
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="homevolt-abc123.local.",
        name="homevolt-abc123._http._tcp.local.",
        port=80,
        properties={},
        type="_http._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Verify host was updated
    assert entry.data[CONF_HOST] == "192.168.1.100"
