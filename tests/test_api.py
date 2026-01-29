"""Tests for Homevolt Local API client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientError

from custom_components.homevolt_local.api import (
    CACHE_EXPIRY,
    CacheEntry,
    HomevoltApi,
    HomevoltApiError,
    HomevoltAuthError,
    HomevoltCommandError,
    HomevoltConnectionError,
    HomevoltNotLocalModeError,
    HomevoltRateLimitError,
)


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock aiohttp session."""
    return MagicMock()


@pytest.fixture
def api(mock_session: MagicMock) -> HomevoltApi:
    """Create an API client with mocked session."""
    return HomevoltApi(
        host="homevolt-test.local",
        password="testpass",
        username="admin",
        session=mock_session,
    )


@pytest.fixture
def api_no_auth(mock_session: MagicMock) -> HomevoltApi:
    """Create an API client without auth."""
    return HomevoltApi(
        host="homevolt-test.local",
        session=mock_session,
    )


class TestHomevoltApiInit:
    """Test HomevoltApi initialization."""

    def test_init_with_auth(self) -> None:
        """Test initialization with authentication."""
        api = HomevoltApi(
            host="192.168.1.100",
            password="secret",
            username="user",
        )
        assert api._host == "http://192.168.1.100"
        assert api._auth is not None
        assert api._auth.login == "user"

    def test_init_without_auth(self) -> None:
        """Test initialization without authentication."""
        api = HomevoltApi(host="homevolt.local")
        assert api._host == "http://homevolt.local"
        assert api._auth is None

    def test_init_with_http_prefix(self) -> None:
        """Test initialization with http:// prefix."""
        api = HomevoltApi(host="http://192.168.1.100")
        assert api._host == "http://192.168.1.100"

    def test_init_with_https_prefix(self) -> None:
        """Test initialization with https:// prefix."""
        api = HomevoltApi(host="https://192.168.1.100")
        assert api._host == "https://192.168.1.100"

    def test_init_strips_trailing_slash(self) -> None:
        """Test initialization strips trailing slash."""
        api = HomevoltApi(host="homevolt.local/")
        assert api._host == "http://homevolt.local"

    def test_init_default_username(self) -> None:
        """Test initialization with default username when password provided."""
        api = HomevoltApi(host="homevolt.local", password="secret")
        assert api._auth is not None
        assert api._auth.login == "admin"


class TestHomevoltApiRequest:
    """Test API request methods."""

    async def test_successful_request(self, api: HomevoltApi, mock_session: MagicMock) -> None:
        """Test successful API request."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok"})
        mock_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_response))

        result = await api._request("/status.json")

        assert result == {"status": "ok"}
        mock_session.get.assert_called_once()

    async def test_auth_error_401(self, api: HomevoltApi, mock_session: MagicMock) -> None:
        """Test 401 response raises auth error."""
        mock_response = AsyncMock()
        mock_response.status = 401

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_response))

        with pytest.raises(HomevoltAuthError):
            await api._request("/status.json")

    async def test_rate_limit_error_429(self, api: HomevoltApi, mock_session: MagicMock) -> None:
        """Test 429 response raises rate limit error."""
        mock_response = AsyncMock()
        mock_response.status = 429

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_response))

        with pytest.raises(HomevoltRateLimitError):
            await api._request("/status.json")

    async def test_server_error_retries(self, api: HomevoltApi, mock_session: MagicMock) -> None:
        """Test server error triggers retry."""
        mock_response_error = AsyncMock()
        mock_response_error.status = 500
        mock_response_error.request_info = MagicMock()
        mock_response_error.history = []

        mock_response_success = AsyncMock()
        mock_response_success.status = 200
        mock_response_success.json = AsyncMock(return_value={"status": "ok"})
        mock_response_success.raise_for_status = MagicMock()

        # First call fails, second succeeds
        mock_session.get = MagicMock(
            side_effect=[
                AsyncContextManager(mock_response_error),
                AsyncContextManager(mock_response_success),
            ]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await api._request("/status.json", retries=1)

        assert result == {"status": "ok"}
        assert mock_session.get.call_count == 2

    async def test_connection_error_after_retries(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test connection error after all retries exhausted."""
        mock_session.get = MagicMock(side_effect=ClientError("Connection failed"))

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(HomevoltConnectionError),
        ):
            await api._request("/status.json", retries=2)

        assert mock_session.get.call_count == 3  # Initial + 2 retries

    async def test_timeout_error_retries(self, api: HomevoltApi, mock_session: MagicMock) -> None:
        """Test timeout error triggers retry."""
        mock_response_success = AsyncMock()
        mock_response_success.status = 200
        mock_response_success.json = AsyncMock(return_value={"status": "ok"})
        mock_response_success.raise_for_status = MagicMock()

        mock_session.get = MagicMock(
            side_effect=[
                TimeoutError(),
                AsyncContextManager(mock_response_success),
            ]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await api._request("/status.json", retries=1)

        assert result == {"status": "ok"}


class TestHomevoltApiCache:
    """Test API caching functionality."""

    async def test_cache_on_success(self, api: HomevoltApi, mock_session: MagicMock) -> None:
        """Test response is cached on success."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok"})
        mock_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_response))

        await api._request_cached("/status.json")

        assert "/status.json" in api._cache
        assert api._cache["/status.json"].data == {"status": "ok"}

    async def test_cache_fallback_on_error(self, api: HomevoltApi, mock_session: MagicMock) -> None:
        """Test cache is used when request fails."""
        import time

        # Pre-populate cache
        api._cache["/status.json"] = CacheEntry(
            data={"cached": "data"},
            timestamp=time.monotonic(),
        )

        mock_session.get = MagicMock(side_effect=ClientError("Connection failed"))

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await api._request_cached("/status.json")

        assert result == {"cached": "data"}

    async def test_expired_cache_not_used(self, api: HomevoltApi, mock_session: MagicMock) -> None:
        """Test expired cache is not used."""
        import time

        # Pre-populate cache with expired entry
        api._cache["/status.json"] = CacheEntry(
            data={"cached": "data"},
            timestamp=time.monotonic() - CACHE_EXPIRY - 1,
        )

        mock_session.get = MagicMock(side_effect=ClientError("Connection failed"))

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(HomevoltConnectionError),
        ):
            await api._request_cached("/status.json")

    def test_clear_cache(self, api: HomevoltApi) -> None:
        """Test cache clearing."""
        import time

        api._cache["/status.json"] = CacheEntry(
            data={"cached": "data"},
            timestamp=time.monotonic(),
        )
        api._cache["/ems.json"] = CacheEntry(
            data={"ems": []},
            timestamp=time.monotonic(),
        )

        api.clear_cache()

        assert len(api._cache) == 0

    def test_get_cached_valid(self, api: HomevoltApi) -> None:
        """Test getting valid cached data."""
        import time

        api._cache["/status.json"] = CacheEntry(
            data={"cached": "data"},
            timestamp=time.monotonic(),
        )

        result = api._get_cached("/status.json")
        assert result == {"cached": "data"}

    def test_get_cached_expired(self, api: HomevoltApi) -> None:
        """Test getting expired cached data returns None."""
        import time

        api._cache["/status.json"] = CacheEntry(
            data={"cached": "data"},
            timestamp=time.monotonic() - CACHE_EXPIRY - 1,
        )

        result = api._get_cached("/status.json")
        assert result is None

    def test_get_cached_missing(self, api: HomevoltApi) -> None:
        """Test getting missing cached data returns None."""
        result = api._get_cached("/status.json")
        assert result is None


class TestHomevoltApiMethods:
    """Test API endpoint methods."""

    async def test_get_status(self, api: HomevoltApi, mock_session: MagicMock) -> None:
        """Test get_status method."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"up_time": 12345})
        mock_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_response))

        result = await api.get_status()

        assert result == {"up_time": 12345}
        call_url = mock_session.get.call_args[0][0]
        assert "/status.json" in call_url

    async def test_get_ems(self, api: HomevoltApi, mock_session: MagicMock) -> None:
        """Test get_ems method."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"ems": []})
        mock_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_response))

        result = await api.get_ems()

        assert result == {"ems": []}
        call_url = mock_session.get.call_args[0][0]
        assert "/ems.json" in call_url

    async def test_get_mains(self, api: HomevoltApi, mock_session: MagicMock) -> None:
        """Test get_mains method."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"frequency": 50.0})
        mock_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_response))

        result = await api.get_mains()

        assert result == {"frequency": 50.0}
        call_url = mock_session.get.call_args[0][0]
        assert "/mains_data.json" in call_url

    async def test_test_connection(self, api: HomevoltApi, mock_session: MagicMock) -> None:
        """Test test_connection uses fewer retries."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok"})
        mock_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_response))

        result = await api.test_connection()

        assert result == {"status": "ok"}

    async def test_get_all_data(self, api: HomevoltApi, mock_session: MagicMock) -> None:
        """Test get_all_data fetches all endpoints."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={})
        mock_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_response))

        result = await api.get_all_data()

        assert "status" in result
        assert "ems" in result
        assert "mains" in result
        assert "params" in result
        assert "schedule" in result

    async def test_get_all_data_partial_failure(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test get_all_data handles partial failures."""
        mock_response_success = AsyncMock()
        mock_response_success.status = 200
        mock_response_success.json = AsyncMock(return_value={"data": "ok"})
        mock_response_success.raise_for_status = MagicMock()

        call_count = 0

        def mock_get_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Fail on second endpoint (ems)
                raise ClientError("Connection failed")
            return AsyncContextManager(mock_response_success)

        mock_session.get = MagicMock(side_effect=mock_get_side_effect)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await api.get_all_data()

        # Should still have data from successful endpoints
        assert "status" in result


class TestHomevoltApiSession:
    """Test API session management."""

    async def test_creates_session_if_none(self) -> None:
        """Test session is created if not provided."""
        api = HomevoltApi(host="homevolt.local")
        assert api._session is None
        assert api._close_session is False

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            session = await api._get_session()

            assert session == mock_session
            assert api._close_session is True

    async def test_uses_provided_session(self, mock_session: MagicMock) -> None:
        """Test provided session is used."""
        api = HomevoltApi(host="homevolt.local", session=mock_session)

        session = await api._get_session()

        assert session == mock_session
        assert api._close_session is False

    async def test_close_session_when_created(self) -> None:
        """Test session is closed when created internally."""
        api = HomevoltApi(host="homevolt.local")
        mock_session = AsyncMock()
        api._session = mock_session
        api._close_session = True

        await api.close()

        mock_session.close.assert_awaited_once()
        assert api._session is None

    async def test_no_close_session_when_provided(self, mock_session: MagicMock) -> None:
        """Test session is not closed when provided externally."""
        api = HomevoltApi(host="homevolt.local", session=mock_session)
        mock_session.close = AsyncMock()

        await api.close()

        mock_session.close.assert_not_awaited()


class TestHomevoltApiSetParam:
    """Test API set_param method."""

    async def test_set_param_success(self, api: HomevoltApi, mock_session: MagicMock) -> None:
        """Test successful set_param call."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="OK")
        mock_response.raise_for_status = MagicMock()

        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_response))

        await api.set_param("settings_local", "true")

        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert "/params.json" in call_args[0][0]
        assert call_args[1]["data"] == {"k": "settings_local", "v": "true", "store": "1"}

    async def test_set_param_auth_error(self, api: HomevoltApi, mock_session: MagicMock) -> None:
        """Test set_param with auth error."""
        mock_response = AsyncMock()
        mock_response.status = 401

        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_response))

        with pytest.raises(HomevoltAuthError):
            await api.set_param("settings_local", "true")


class TestHomevoltApiConsoleCommand:
    """Test API console command methods."""

    async def test_send_console_command_success(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test successful console command with JSON response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(
            return_value='{"command": "sched_clear", "output": "Schedule cleared", "exit_code": 0}'
        )
        mock_response.raise_for_status = MagicMock()

        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_response))

        result = await api.send_console_command("sched_clear")

        assert result == {"command": "sched_clear", "output": "Schedule cleared", "exit_code": 0}
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert "/console.json" in call_args[0][0]
        assert call_args[1]["data"] == {"cmd": "sched_clear"}

    async def test_send_console_command_plain_text_response(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test console command with plain text response (non-JSON)."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="OK")
        mock_response.raise_for_status = MagicMock()

        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_response))

        result = await api.send_console_command("sched_clear")

        assert result == {"command": "sched_clear", "output": "OK", "exit_code": 0}

    async def test_send_console_command_auth_error(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test console command with auth error."""
        mock_response = AsyncMock()
        mock_response.status = 401

        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_response))

        with pytest.raises(HomevoltAuthError):
            await api.send_console_command("sched_clear")

    async def test_send_console_command_rate_limit_error(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test console command with rate limit error."""
        mock_response = AsyncMock()
        mock_response.status = 429

        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_response))

        with pytest.raises(HomevoltRateLimitError):
            await api.send_console_command("sched_clear")

    async def test_send_console_command_invalid_command(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test console command with invalid command (400 error)."""
        mock_response = AsyncMock()
        mock_response.status = 400

        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_response))

        with pytest.raises(HomevoltApiError) as exc_info:
            await api.send_console_command("invalid_cmd")

        assert "Invalid command" in str(exc_info.value)

    async def test_send_console_command_connection_error(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test console command with connection error."""
        mock_session.post = MagicMock(side_effect=ClientError("Connection failed"))

        with pytest.raises(HomevoltConnectionError):
            await api.send_console_command("sched_clear")

    async def test_send_console_command_device_error(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test console command raises error when device returns non-zero exit code."""
        error_response = (
            "esp32> sched_set 3 --from 2024-01-15T02:00:00 --to 2024-01-15T06:00:00\n"
            "Missing power setpoint\n"
            "Command 'sched_set 3 ...' returned non-zero error code: 0x2 (ERROR)"
        )
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=error_response)
        mock_response.raise_for_status = MagicMock()

        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_response))

        with pytest.raises(HomevoltCommandError) as exc_info:
            await api.send_console_command("sched_set 3")

        assert "Missing power setpoint" in str(exc_info.value)

    async def test_clear_schedule_calls_correct_command(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test clear_schedule calls send_console_command with correct command."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(
            return_value='{"command": "sched_clear", "output": "Schedule cleared", "exit_code": 0}'
        )
        mock_response.raise_for_status = MagicMock()

        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_response))

        result = await api.clear_schedule()

        assert result["command"] == "sched_clear"
        call_args = mock_session.post.call_args
        assert call_args[1]["data"] == {"cmd": "sched_clear"}

    async def test_send_console_command_no_auth(
        self, api_no_auth: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test console command without auth."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(
            return_value='{"command": "sched_clear", "output": "OK", "exit_code": 0}'
        )
        mock_response.raise_for_status = MagicMock()

        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_response))

        result = await api_no_auth.send_console_command("sched_clear")

        assert result["exit_code"] == 0
        # Verify no auth was passed
        call_kwargs = mock_session.post.call_args[1]
        assert "auth" not in call_kwargs


class TestHomevoltApiSetIdle:
    """Test API set_idle method."""

    async def test_set_idle_success_when_local_mode(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test set_idle succeeds when device is in local mode."""
        # Mock get_schedule response (GET)
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": True})
        mock_schedule_response.raise_for_status = MagicMock()

        # Mock console command response (POST)
        mock_console_response = AsyncMock()
        mock_console_response.status = 200
        mock_console_response.text = AsyncMock(
            return_value='{"command": "sched_set 0", "output": "OK", "exit_code": 0}'
        )
        mock_console_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))
        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_console_response))

        result = await api.set_idle()

        assert result["command"] == "sched_set 0"
        assert result["exit_code"] == 0
        # Verify console command was called with correct data
        call_args = mock_session.post.call_args
        assert call_args[1]["data"] == {"cmd": "sched_set 0"}

    async def test_set_idle_with_offline_parameter(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test set_idle with offline parameter."""
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": True})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_console_response = AsyncMock()
        mock_console_response.status = 200
        mock_console_response.text = AsyncMock(
            return_value='{"command": "sched_set 0 --offline", "output": "OK", "exit_code": 0}'
        )
        mock_console_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))
        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_console_response))

        await api.set_idle(offline=True)

        call_args = mock_session.post.call_args
        assert call_args[1]["data"] == {"cmd": "sched_set 0 --offline"}

    async def test_set_idle_raises_error_when_not_local_mode(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test set_idle raises HomevoltNotLocalModeError when not in local mode."""
        # Mock get_schedule response with local_mode=False
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": False})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))

        with pytest.raises(HomevoltNotLocalModeError) as exc_info:
            await api.set_idle()

        assert "not in local mode" in str(exc_info.value)
        # Verify no POST was made
        mock_session.post.assert_not_called()

    async def test_set_idle_raises_error_when_local_mode_missing(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test set_idle raises error when local_mode field is missing."""
        # Mock get_schedule response without local_mode
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))

        with pytest.raises(HomevoltNotLocalModeError):
            await api.set_idle()

        mock_session.post.assert_not_called()


class TestHomevoltApiSetCharge:
    """Test API set_charge method."""

    async def test_set_charge_success(self, api: HomevoltApi, mock_session: MagicMock) -> None:
        """Test set_charge succeeds when device is in local mode."""
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": True})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_console_response = AsyncMock()
        mock_console_response.status = 200
        mock_console_response.text = AsyncMock(
            return_value='{"command": "sched_set 1", "output": "OK", "exit_code": 0}'
        )
        mock_console_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))
        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_console_response))

        await api.set_charge()

        call_args = mock_session.post.call_args
        assert call_args[1]["data"] == {"cmd": "sched_set 1"}

    async def test_set_charge_with_all_parameters(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test set_charge with setpoint and SOC parameters."""
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": True})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_console_response = AsyncMock()
        mock_console_response.status = 200
        mock_console_response.text = AsyncMock(return_value='{"exit_code": 0}')
        mock_console_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))
        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_console_response))

        await api.set_charge(setpoint=5000, min_soc=10, max_soc=90)

        call_args = mock_session.post.call_args
        assert call_args[1]["data"] == {"cmd": "sched_set 1 -s 5000 --min 10 --max 90"}

    async def test_set_charge_raises_error_when_not_local_mode(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test set_charge raises error when not in local mode."""
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": False})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))

        with pytest.raises(HomevoltNotLocalModeError):
            await api.set_charge()


class TestHomevoltApiSetDischarge:
    """Test API set_discharge method."""

    async def test_set_discharge_success(self, api: HomevoltApi, mock_session: MagicMock) -> None:
        """Test set_discharge succeeds when device is in local mode."""
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": True})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_console_response = AsyncMock()
        mock_console_response.status = 200
        mock_console_response.text = AsyncMock(return_value='{"exit_code": 0}')
        mock_console_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))
        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_console_response))

        await api.set_discharge()

        call_args = mock_session.post.call_args
        assert call_args[1]["data"] == {"cmd": "sched_set 2"}

    async def test_set_discharge_with_all_parameters(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test set_discharge with setpoint and SOC parameters."""
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": True})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_console_response = AsyncMock()
        mock_console_response.status = 200
        mock_console_response.text = AsyncMock(return_value='{"exit_code": 0}')
        mock_console_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))
        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_console_response))

        await api.set_discharge(setpoint=3000, min_soc=20, max_soc=80)

        call_args = mock_session.post.call_args
        assert call_args[1]["data"] == {"cmd": "sched_set 2 -s 3000 --min 20 --max 80"}


class TestHomevoltApiSetGridCharge:
    """Test API set_grid_charge method."""

    async def test_set_grid_charge_success(self, api: HomevoltApi, mock_session: MagicMock) -> None:
        """Test set_grid_charge succeeds when device is in local mode."""
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": True})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_console_response = AsyncMock()
        mock_console_response.status = 200
        mock_console_response.text = AsyncMock(return_value='{"exit_code": 0}')
        mock_console_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))
        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_console_response))

        await api.set_grid_charge()

        call_args = mock_session.post.call_args
        assert call_args[1]["data"] == {"cmd": "sched_set 3"}

    async def test_set_grid_charge_with_all_parameters(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test set_grid_charge with setpoint and SOC parameters."""
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": True})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_console_response = AsyncMock()
        mock_console_response.status = 200
        mock_console_response.text = AsyncMock(return_value='{"exit_code": 0}')
        mock_console_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))
        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_console_response))

        await api.set_grid_charge(setpoint=5000, min_soc=10, max_soc=95)

        call_args = mock_session.post.call_args
        assert call_args[1]["data"] == {"cmd": "sched_set 3 -s 5000 --min 10 --max 95"}

    async def test_set_grid_charge_raises_error_when_not_local_mode(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test set_grid_charge raises error when not in local mode."""
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": False})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))

        with pytest.raises(HomevoltNotLocalModeError):
            await api.set_grid_charge()


class TestHomevoltApiSetGridDischarge:
    """Test API set_grid_discharge method."""

    async def test_set_grid_discharge_success(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test set_grid_discharge succeeds when device is in local mode."""
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": True})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_console_response = AsyncMock()
        mock_console_response.status = 200
        mock_console_response.text = AsyncMock(return_value='{"exit_code": 0}')
        mock_console_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))
        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_console_response))

        await api.set_grid_discharge()

        call_args = mock_session.post.call_args
        assert call_args[1]["data"] == {"cmd": "sched_set 4"}

    async def test_set_grid_discharge_with_all_parameters(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test set_grid_discharge with setpoint and SOC parameters."""
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": True})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_console_response = AsyncMock()
        mock_console_response.status = 200
        mock_console_response.text = AsyncMock(return_value='{"exit_code": 0}')
        mock_console_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))
        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_console_response))

        await api.set_grid_discharge(setpoint=4000, min_soc=15, max_soc=85)

        call_args = mock_session.post.call_args
        assert call_args[1]["data"] == {"cmd": "sched_set 4 -s 4000 --min 15 --max 85"}


class TestHomevoltApiSetGridChargeDischarge:
    """Test API set_grid_charge_discharge method."""

    async def test_set_grid_charge_discharge_success(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test set_grid_charge_discharge succeeds when device is in local mode."""
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": True})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_console_response = AsyncMock()
        mock_console_response.status = 200
        mock_console_response.text = AsyncMock(return_value='{"exit_code": 0}')
        mock_console_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))
        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_console_response))

        await api.set_grid_charge_discharge(setpoint=5000)

        call_args = mock_session.post.call_args
        assert call_args[1]["data"] == {"cmd": "sched_set 5 -s 5000"}

    async def test_set_grid_charge_discharge_with_all_parameters(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test set_grid_charge_discharge with all parameters."""
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": True})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_console_response = AsyncMock()
        mock_console_response.status = 200
        mock_console_response.text = AsyncMock(return_value='{"exit_code": 0}')
        mock_console_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))
        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_console_response))

        await api.set_grid_charge_discharge(
            setpoint=5000,
            charge_setpoint=3000,
            discharge_setpoint=4000,
            min_soc=10,
            max_soc=90,
        )

        call_args = mock_session.post.call_args
        assert call_args[1]["data"] == {
            "cmd": "sched_set 5 -s 5000 -c 3000 -d 4000 --min 10 --max 90"
        }

    async def test_set_grid_charge_discharge_raises_error_when_not_local_mode(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test set_grid_charge_discharge raises error when not in local mode."""
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": False})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))

        with pytest.raises(HomevoltNotLocalModeError):
            await api.set_grid_charge_discharge(setpoint=5000)


class TestHomevoltApiBuildScheduleCommand:
    """Test API _build_schedule_command method."""

    def test_build_schedule_command_type_only(self, api: HomevoltApi) -> None:
        """Test building command with type only."""
        entry = {"type": 1}
        result = api._build_schedule_command(entry)
        assert result == "1"

    def test_build_schedule_command_with_time(self, api: HomevoltApi) -> None:
        """Test building command with time parameters."""
        entry = {
            "type": 1,
            "from_time": "2024-01-15T23:00:00",
            "to_time": "2024-01-16T07:00:00",
        }
        result = api._build_schedule_command(entry)
        assert result == "1 --from 2024-01-15T23:00:00 --to 2024-01-16T07:00:00"

    def test_build_schedule_command_with_soc(self, api: HomevoltApi) -> None:
        """Test building command with SOC constraints."""
        entry = {"type": 2, "min_soc": 20, "max_soc": 80}
        result = api._build_schedule_command(entry)
        assert result == "2 --min 20 --max 80"

    def test_build_schedule_command_with_power(self, api: HomevoltApi) -> None:
        """Test building command with power settings."""
        entry = {"type": 5, "setpoint": 3000, "max_charge": 4000, "max_discharge": 5000}
        result = api._build_schedule_command(entry)
        assert result == "5 -s 3000 -c 4000 -d 5000"

    def test_build_schedule_command_with_limits(self, api: HomevoltApi) -> None:
        """Test building command with grid limits."""
        entry = {"type": 8, "import_limit": 1000, "export_limit": 2000}
        result = api._build_schedule_command(entry)
        assert result == "8 -l 1000 -x 2000"

    def test_build_schedule_command_all_parameters(self, api: HomevoltApi) -> None:
        """Test building command with all parameters."""
        entry = {
            "type": 1,
            "from_time": "2024-01-15T23:00:00",
            "to_time": "2024-01-16T07:00:00",
            "min_soc": 10,
            "max_soc": 90,
            "setpoint": 3000,
            "max_charge": 4000,
            "max_discharge": 5000,
            "import_limit": 1000,
            "export_limit": 2000,
        }
        result = api._build_schedule_command(entry)
        assert (
            result == "1 --from 2024-01-15T23:00:00 --to 2024-01-16T07:00:00 "
            "--min 10 --max 90 -s 3000 -c 4000 -d 5000 -l 1000 -x 2000"
        )


class TestHomevoltApiSetSchedule:
    """Test API set_schedule method."""

    async def test_set_schedule_single_entry(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test set_schedule with single entry uses sched_set."""
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": True})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_console_response = AsyncMock()
        mock_console_response.status = 200
        mock_console_response.text = AsyncMock(return_value='{"exit_code": 0}')
        mock_console_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))
        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_console_response))

        entries = [{"type": 1, "max_charge": 3000, "max_soc": 80}]
        results = await api.set_schedule(entries)

        assert len(results) == 1
        call_args = mock_session.post.call_args
        assert call_args[1]["data"] == {"cmd": "sched_set 1 --max 80 -c 3000"}

    async def test_set_schedule_multiple_entries(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test set_schedule with multiple entries uses sched_set then sched_add."""
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": True})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_console_response = AsyncMock()
        mock_console_response.status = 200
        mock_console_response.text = AsyncMock(return_value='{"exit_code": 0}')
        mock_console_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))
        mock_session.post = MagicMock(return_value=AsyncContextManager(mock_console_response))

        entries = [
            {"type": 1, "from_time": "2024-01-15T23:00:00", "to_time": "2024-01-16T07:00:00"},
            {"type": 2, "from_time": "2024-01-16T17:00:00", "to_time": "2024-01-16T20:00:00"},
        ]
        results = await api.set_schedule(entries)

        assert len(results) == 2
        assert mock_session.post.call_count == 2

        # First call should use sched_set
        first_call_args = mock_session.post.call_args_list[0]
        assert "sched_set 1" in first_call_args[1]["data"]["cmd"]

        # Second call should use sched_add
        second_call_args = mock_session.post.call_args_list[1]
        assert "sched_add 2" in second_call_args[1]["data"]["cmd"]

    async def test_set_schedule_empty_entries_raises_error(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test set_schedule with empty entries raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await api.set_schedule([])

        assert "empty" in str(exc_info.value)

    async def test_set_schedule_raises_error_when_not_local_mode(
        self, api: HomevoltApi, mock_session: MagicMock
    ) -> None:
        """Test set_schedule raises error when not in local mode."""
        mock_schedule_response = AsyncMock()
        mock_schedule_response.status = 200
        mock_schedule_response.json = AsyncMock(return_value={"local_mode": False})
        mock_schedule_response.raise_for_status = MagicMock()

        mock_session.get = MagicMock(return_value=AsyncContextManager(mock_schedule_response))

        with pytest.raises(HomevoltNotLocalModeError):
            await api.set_schedule([{"type": 1}])

        # Verify no POST was made
        mock_session.post.assert_not_called()


class AsyncContextManager:
    """Async context manager wrapper for mock responses."""

    def __init__(self, response):
        """Initialize with response."""
        self.response = response

    async def __aenter__(self):
        """Enter context."""
        return self.response

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        pass
