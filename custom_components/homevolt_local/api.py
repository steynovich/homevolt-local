"""API client for Homevolt Local."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, cast

import aiohttp
from aiohttp import BasicAuth, ClientError, ClientResponseError, ClientTimeout

from .const import (
    DEFAULT_USERNAME,
    ENDPOINT_CONSOLE,
    ENDPOINT_EMS,
    ENDPOINT_ERROR_REPORT,
    ENDPOINT_MAINS,
    ENDPOINT_NODES,
    ENDPOINT_OTA_MANIFEST,
    ENDPOINT_PARAMS,
    ENDPOINT_SCHEDULE,
    ENDPOINT_STATUS,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = ClientTimeout(total=10)

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
RETRY_MAX_DELAY = 30.0  # seconds
RETRY_JITTER = 0.5  # random jitter factor (0-0.5)

# Cache configuration
CACHE_EXPIRY = 600  # 10 minutes in seconds


@dataclass
class CacheEntry:
    """Cached API response with timestamp."""

    data: dict[str, Any]
    timestamp: float


class HomevoltApiError(Exception):
    """Base exception for Homevolt API errors."""


class HomevoltAuthError(HomevoltApiError):
    """Authentication error."""


class HomevoltRateLimitError(HomevoltApiError):
    """Rate limit error (too many failed auth attempts)."""


class HomevoltConnectionError(HomevoltApiError):
    """Connection error."""


class HomevoltNotLocalModeError(HomevoltApiError):
    """Raised when trying to send schedule while not in local mode."""


class HomevoltCommandError(HomevoltApiError):
    """Raised when a device console command fails."""


class HomevoltApi:
    """API client for Homevolt Local."""

    def __init__(
        self,
        host: str,
        password: str | None = None,
        username: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the API client."""
        self._host = host.rstrip("/")
        self._session = session
        self._close_session = False
        self._cache: dict[str, CacheEntry] = {}

        # Only use auth if password is provided
        if password:
            self._auth: BasicAuth | None = BasicAuth(username or DEFAULT_USERNAME, password)
        else:
            self._auth = None

        # Ensure host has protocol
        if not self._host.startswith(("http://", "https://")):
            self._host = f"http://{self._host}"

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._close_session = True
        return self._session

    async def close(self) -> None:
        """Close the session."""
        if self._close_session and self._session:
            await self._session.close()
            self._session = None

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()

    async def _request(self, endpoint: str, retries: int = MAX_RETRIES) -> dict[str, Any]:
        """Make a request to the API with exponential backoff retry."""
        session = await self._get_session()
        url = f"{self._host}{endpoint}"

        kwargs: dict[str, Any] = {"timeout": DEFAULT_TIMEOUT}
        if self._auth:
            kwargs["auth"] = self._auth

        last_error: Exception | None = None

        for attempt in range(retries + 1):
            try:
                async with session.get(url, **kwargs) as response:
                    if response.status == 401:
                        raise HomevoltAuthError(f"Authentication required for {url}")
                    if response.status == 429:
                        raise HomevoltRateLimitError(
                            f"Rate limited for {url} (too many failed auth attempts)"
                        )
                    if response.status >= 500:
                        raise ClientResponseError(
                            response.request_info,
                            response.history,
                            status=response.status,
                            message=f"Server error: {response.status}",
                        )
                    response.raise_for_status()
                    return cast(dict[str, Any], await response.json())
            except (HomevoltAuthError, HomevoltRateLimitError):
                # Don't retry auth or rate limit errors
                raise
            except ClientResponseError as err:
                if err.status == 401:
                    raise HomevoltAuthError(f"Authentication required for {url}") from err
                if err.status == 429:
                    raise HomevoltRateLimitError(
                        f"Rate limited for {url} (too many failed auth attempts)"
                    ) from err
                if err.status >= 500:
                    last_error = err
                    # Retry on server errors
                else:
                    raise HomevoltApiError(f"API error {err.status} for {url}") from err
            except (TimeoutError, ClientError) as err:
                last_error = err

            # If we get here, we need to retry
            if attempt < retries:
                delay = min(
                    RETRY_BASE_DELAY * (2**attempt),
                    RETRY_MAX_DELAY,
                )
                # Add jitter to prevent thundering herd
                delay *= 1 + random.uniform(0, RETRY_JITTER)
                _LOGGER.debug(
                    "Request to %s failed (attempt %d/%d), retrying in %.1fs: %s",
                    url,
                    attempt + 1,
                    retries + 1,
                    delay,
                    last_error,
                )
                await asyncio.sleep(delay)

        # All retries exhausted
        if last_error:
            raise HomevoltConnectionError(
                f"Connection error for {url} after {retries + 1} attempts: {last_error}"
            ) from last_error
        raise HomevoltConnectionError(f"Connection error for {url} after {retries + 1} attempts")

    async def _request_cached(self, endpoint: str, retries: int = MAX_RETRIES) -> dict[str, Any]:
        """Make a request with cache fallback on failure."""
        url = f"{self._host}{endpoint}"
        try:
            data = await self._request(endpoint, retries)
            # Update cache on success
            self._cache[endpoint] = CacheEntry(data=data, timestamp=time.monotonic())
            return data
        except (HomevoltAuthError, HomevoltRateLimitError):
            # Don't use cache for auth or rate limit errors
            raise
        except HomevoltApiError as err:
            # Check if we have a valid cached response
            cached = self._cache.get(endpoint)
            if cached and (time.monotonic() - cached.timestamp) < CACHE_EXPIRY:
                _LOGGER.debug(
                    "Request to %s failed, using cached data (age: %.0fs): %s",
                    url,
                    time.monotonic() - cached.timestamp,
                    err,
                )
                return cached.data
            # No valid cache, re-raise the error
            raise

    def _get_cached(self, endpoint: str) -> dict[str, Any] | None:
        """Get cached data for an endpoint if still valid."""
        cached = self._cache.get(endpoint)
        if cached and (time.monotonic() - cached.timestamp) < CACHE_EXPIRY:
            return cached.data
        return None

    async def get_status(self) -> dict[str, Any]:
        """Get system status."""
        return await self._request_cached(ENDPOINT_STATUS)

    async def get_ems(self) -> dict[str, Any]:
        """Get EMS (Energy Management System) data."""
        return await self._request_cached(ENDPOINT_EMS)

    async def get_nodes(self) -> dict[str, Any]:
        """Get connected nodes."""
        return await self._request_cached(ENDPOINT_NODES)

    async def get_mains(self) -> dict[str, Any]:
        """Get mains voltage and frequency data."""
        return await self._request_cached(ENDPOINT_MAINS)

    async def get_params(self) -> dict[str, Any]:
        """Get configurable parameters."""
        return await self._request_cached(ENDPOINT_PARAMS)

    async def get_schedule(self) -> dict[str, Any]:
        """Get charging schedules."""
        return await self._request_cached(ENDPOINT_SCHEDULE)

    async def get_error_report(self) -> dict[str, Any]:
        """Get error report."""
        return await self._request_cached(ENDPOINT_ERROR_REPORT)

    async def get_ota_manifest(self) -> dict[str, Any]:
        """Get OTA manifest with version info."""
        return await self._request_cached(ENDPOINT_OTA_MANIFEST)

    async def test_connection(self) -> dict[str, Any]:
        """Test the connection and return status."""
        # Use fewer retries for connection test (faster feedback during setup)
        return await self._request(ENDPOINT_STATUS, retries=1)

    async def get_all_data(self) -> dict[str, Any]:
        """Get all data from the device."""
        data: dict[str, Any] = {}

        # Fetch all endpoints, continue on individual failures
        endpoints = [
            ("status", self.get_status),
            ("ems", self.get_ems),
            ("mains", self.get_mains),
            ("params", self.get_params),
            ("schedule", self.get_schedule),
            ("ota_manifest", self.get_ota_manifest),
        ]

        for key, method in endpoints:
            try:
                data[key] = await method()
            except HomevoltApiError as err:
                _LOGGER.debug("Failed to fetch %s: %s", key, err)
                data[key] = {}

        return data

    async def set_param(self, key: str, value: str) -> None:
        """Set a parameter value via POST to /params.json.

        Always persists to non-volatile storage (store=1).
        """
        session = await self._get_session()
        url = f"{self._host}{ENDPOINT_PARAMS}"

        kwargs: dict[str, Any] = {"timeout": DEFAULT_TIMEOUT}
        if self._auth:
            kwargs["auth"] = self._auth

        # POST with form data: k=<key>&v=<value>&store=1
        form_data = {"k": key, "v": value, "store": "1"}

        _LOGGER.debug("POST %s with data: %s", url, form_data)

        try:
            async with session.post(url, data=form_data, **kwargs) as response:
                if response.status == 401:
                    raise HomevoltAuthError(f"Authentication required for {url}")
                if response.status == 429:
                    raise HomevoltRateLimitError(
                        f"Rate limited for {url} (too many failed auth attempts)"
                    )
                response.raise_for_status()
                # Log the response for debugging
                response_text = await response.text()
                _LOGGER.debug(
                    "POST %s response (status=%s): %s", url, response.status, response_text
                )
        except ClientResponseError as err:
            if err.status == 401:
                raise HomevoltAuthError(f"Authentication required for {url}") from err
            if err.status == 429:
                raise HomevoltRateLimitError(
                    f"Rate limited for {url} (too many failed auth attempts)"
                ) from err
            raise HomevoltApiError(f"API error {err.status} for {url}") from err
        except (TimeoutError, ClientError) as err:
            raise HomevoltConnectionError(f"Connection error for {url}: {err}") from err

    async def send_console_command(self, command: str) -> dict[str, Any]:
        """Send a console command to the device via POST to /console.json.

        Args:
            command: The console command to send (e.g., "sched_clear")

        Returns:
            Response dict with keys: command, output, exit_code
        """
        session = await self._get_session()
        url = f"{self._host}{ENDPOINT_CONSOLE}"

        kwargs: dict[str, Any] = {
            "timeout": DEFAULT_TIMEOUT,
            "headers": {"Accept": "application/json"},
        }
        if self._auth:
            kwargs["auth"] = self._auth

        form_data = {"cmd": command}

        _LOGGER.debug("POST %s with data: %s", url, form_data)

        try:
            async with session.post(url, data=form_data, **kwargs) as response:
                if response.status == 401:
                    raise HomevoltAuthError(f"Authentication required for {url}")
                if response.status == 429:
                    raise HomevoltRateLimitError(
                        f"Rate limited for {url} (too many failed auth attempts)"
                    )
                if response.status == 400:
                    raise HomevoltApiError(f"Invalid command '{command}' for {url}")
                response.raise_for_status()
                # Read response as text first to handle non-JSON responses
                response_text = await response.text()
                _LOGGER.debug(
                    "POST %s response (status=%s): %s", url, response.status, response_text
                )
                # Try to parse as JSON, return raw text if not valid JSON
                try:
                    result = json.loads(response_text)
                    return cast(dict[str, Any], result)
                except json.JSONDecodeError:
                    # Device returned non-JSON response - check for command errors
                    # Error format: "Command '...' returned non-zero error code: 0xN (ERROR)"
                    if "returned non-zero error code" in response_text:
                        # Extract error message from lines before the error code line
                        lines = response_text.strip().split("\n")
                        error_lines = []
                        for line in lines:
                            if "returned non-zero error code" in line:
                                break
                            # Skip the command echo line (starts with "esp32>")
                            if not line.startswith("esp32>"):
                                error_lines.append(line.strip())
                        error_msg = " ".join(error_lines).strip() or "Command failed"
                        raise HomevoltCommandError(error_msg) from None
                    return {"command": command, "output": response_text.strip(), "exit_code": 0}
        except ClientResponseError as err:
            if err.status == 401:
                raise HomevoltAuthError(f"Authentication required for {url}") from err
            if err.status == 429:
                raise HomevoltRateLimitError(
                    f"Rate limited for {url} (too many failed auth attempts)"
                ) from err
            if err.status == 400:
                raise HomevoltApiError(f"Invalid command '{command}' for {url}") from err
            raise HomevoltApiError(f"API error {err.status} for {url}") from err
        except (TimeoutError, ClientError) as err:
            raise HomevoltConnectionError(f"Connection error for {url}: {err}") from err

    async def clear_schedule(self) -> dict[str, Any]:
        """Clear all scheduled entries on the device.

        Returns:
            Response dict with keys: command, output, exit_code
        """
        return await self.send_console_command("sched_clear")

    async def reboot(self) -> dict[str, Any]:
        """Reboot the device via hardware reset."""
        return await self.send_console_command("reset_hard")

    async def set_idle(self, offline: bool = False) -> dict[str, Any]:
        """Set battery to idle mode (no charge/discharge).

        Checks that the device is in local mode before sending the command.

        Args:
            offline: If True, take inverter offline during idle mode

        Returns:
            Response dict with keys: command, output, exit_code

        Raises:
            HomevoltNotLocalModeError: If device is not in local mode
        """
        schedule = await self.get_schedule()
        if not schedule.get("local_mode", False):
            raise HomevoltNotLocalModeError(
                "Cannot set schedule: device is not in local mode. "
                "Enable local mode first to prevent remote overrides."
            )
        cmd = "sched_set 0"
        if offline:
            cmd += " --offline"
        return await self.send_console_command(cmd)

    async def set_charge(
        self,
        setpoint: int | None = None,
        min_soc: int | None = None,
        max_soc: int | None = None,
    ) -> dict[str, Any]:
        """Set battery to charge mode (inverter charge from grid/solar).

        Checks that the device is in local mode before sending the command.

        Args:
            setpoint: Optional power setpoint in watts
            min_soc: Optional minimum state of charge (%)
            max_soc: Optional maximum state of charge (%)

        Returns:
            Response dict with keys: command, output, exit_code

        Raises:
            HomevoltNotLocalModeError: If device is not in local mode
        """
        schedule = await self.get_schedule()
        if not schedule.get("local_mode", False):
            raise HomevoltNotLocalModeError(
                "Cannot set schedule: device is not in local mode. "
                "Enable local mode first to prevent remote overrides."
            )
        cmd = "sched_set 1"
        if setpoint is not None:
            cmd += f" -s {setpoint}"
        if min_soc is not None:
            cmd += f" --min {min_soc}"
        if max_soc is not None:
            cmd += f" --max {max_soc}"
        return await self.send_console_command(cmd)

    async def set_discharge(
        self,
        setpoint: int | None = None,
        min_soc: int | None = None,
        max_soc: int | None = None,
    ) -> dict[str, Any]:
        """Set battery to discharge mode (inverter discharge to home/grid).

        Checks that the device is in local mode before sending the command.

        Args:
            setpoint: Optional power setpoint in watts
            min_soc: Optional minimum state of charge (%)
            max_soc: Optional maximum state of charge (%)

        Returns:
            Response dict with keys: command, output, exit_code

        Raises:
            HomevoltNotLocalModeError: If device is not in local mode
        """
        schedule = await self.get_schedule()
        if not schedule.get("local_mode", False):
            raise HomevoltNotLocalModeError(
                "Cannot set schedule: device is not in local mode. "
                "Enable local mode first to prevent remote overrides."
            )
        cmd = "sched_set 2"
        if setpoint is not None:
            cmd += f" -s {setpoint}"
        if min_soc is not None:
            cmd += f" --min {min_soc}"
        if max_soc is not None:
            cmd += f" --max {max_soc}"
        return await self.send_console_command(cmd)

    async def set_grid_charge(
        self,
        setpoint: int | None = None,
        min_soc: int | None = None,
        max_soc: int | None = None,
    ) -> dict[str, Any]:
        """Set battery to grid charge mode (force charge from grid).

        Checks that the device is in local mode before sending the command.

        Args:
            setpoint: Optional power setpoint in watts
            min_soc: Optional minimum state of charge (%)
            max_soc: Optional maximum state of charge (%)

        Returns:
            Response dict with keys: command, output, exit_code

        Raises:
            HomevoltNotLocalModeError: If device is not in local mode
        """
        schedule = await self.get_schedule()
        if not schedule.get("local_mode", False):
            raise HomevoltNotLocalModeError(
                "Cannot set schedule: device is not in local mode. "
                "Enable local mode first to prevent remote overrides."
            )
        cmd = "sched_set 3"
        if setpoint is not None:
            cmd += f" -s {setpoint}"
        if min_soc is not None:
            cmd += f" --min {min_soc}"
        if max_soc is not None:
            cmd += f" --max {max_soc}"
        return await self.send_console_command(cmd)

    async def set_grid_discharge(
        self,
        setpoint: int | None = None,
        min_soc: int | None = None,
        max_soc: int | None = None,
    ) -> dict[str, Any]:
        """Set battery to grid discharge mode (force discharge to grid).

        Checks that the device is in local mode before sending the command.

        Args:
            setpoint: Optional power setpoint in watts
            min_soc: Optional minimum state of charge (%)
            max_soc: Optional maximum state of charge (%)

        Returns:
            Response dict with keys: command, output, exit_code

        Raises:
            HomevoltNotLocalModeError: If device is not in local mode
        """
        schedule = await self.get_schedule()
        if not schedule.get("local_mode", False):
            raise HomevoltNotLocalModeError(
                "Cannot set schedule: device is not in local mode. "
                "Enable local mode first to prevent remote overrides."
            )
        cmd = "sched_set 4"
        if setpoint is not None:
            cmd += f" -s {setpoint}"
        if min_soc is not None:
            cmd += f" --min {min_soc}"
        if max_soc is not None:
            cmd += f" --max {max_soc}"
        return await self.send_console_command(cmd)

    async def set_grid_charge_discharge(
        self,
        setpoint: int | None = None,
        charge_setpoint: int | None = None,
        discharge_setpoint: int | None = None,
        min_soc: int | None = None,
        max_soc: int | None = None,
    ) -> dict[str, Any]:
        """Set battery to grid charge/discharge mode (bidirectional grid control).

        Checks that the device is in local mode before sending the command.

        Args:
            setpoint: Required power setpoint in watts
            charge_setpoint: Optional maximum charge power in watts
            discharge_setpoint: Optional maximum discharge power in watts
            min_soc: Optional minimum state of charge (%)
            max_soc: Optional maximum state of charge (%)

        Returns:
            Response dict with keys: command, output, exit_code

        Raises:
            HomevoltNotLocalModeError: If device is not in local mode
        """
        schedule = await self.get_schedule()
        if not schedule.get("local_mode", False):
            raise HomevoltNotLocalModeError(
                "Cannot set schedule: device is not in local mode. "
                "Enable local mode first to prevent remote overrides."
            )
        cmd = "sched_set 5"
        if setpoint is not None:
            cmd += f" -s {setpoint}"
        if charge_setpoint is not None:
            cmd += f" -c {charge_setpoint}"
        if discharge_setpoint is not None:
            cmd += f" -d {discharge_setpoint}"
        if min_soc is not None:
            cmd += f" --min {min_soc}"
        if max_soc is not None:
            cmd += f" --max {max_soc}"
        return await self.send_console_command(cmd)

    async def set_solar_charge(
        self,
        setpoint: int | None = None,
        min_soc: int | None = None,
        max_soc: int | None = None,
    ) -> dict[str, Any]:
        """Set battery to solar charge mode (charge from solar production only).

        Checks that the device is in local mode before sending the command.

        Args:
            setpoint: Optional power setpoint in watts
            min_soc: Optional minimum state of charge (%)
            max_soc: Optional maximum state of charge (%)

        Returns:
            Response dict with keys: command, output, exit_code

        Raises:
            HomevoltNotLocalModeError: If device is not in local mode
        """
        schedule = await self.get_schedule()
        if not schedule.get("local_mode", False):
            raise HomevoltNotLocalModeError(
                "Cannot set schedule: device is not in local mode. "
                "Enable local mode first to prevent remote overrides."
            )
        cmd = "sched_set 7"
        if setpoint is not None:
            cmd += f" -s {setpoint}"
        if min_soc is not None:
            cmd += f" --min {min_soc}"
        if max_soc is not None:
            cmd += f" --max {max_soc}"
        return await self.send_console_command(cmd)

    async def set_solar_charge_discharge(
        self,
        setpoint: int | None = None,
        charge_setpoint: int | None = None,
        discharge_setpoint: int | None = None,
        min_soc: int | None = None,
        max_soc: int | None = None,
    ) -> dict[str, Any]:
        """Set battery to solar charge/discharge mode (solar-based grid management).

        Checks that the device is in local mode before sending the command.

        Args:
            setpoint: Optional power setpoint in watts
            charge_setpoint: Optional maximum charge power in watts
            discharge_setpoint: Optional maximum discharge power in watts
            min_soc: Optional minimum state of charge (%)
            max_soc: Optional maximum state of charge (%)

        Returns:
            Response dict with keys: command, output, exit_code

        Raises:
            HomevoltNotLocalModeError: If device is not in local mode
        """
        schedule = await self.get_schedule()
        if not schedule.get("local_mode", False):
            raise HomevoltNotLocalModeError(
                "Cannot set schedule: device is not in local mode. "
                "Enable local mode first to prevent remote overrides."
            )
        cmd = "sched_set 8"
        if setpoint is not None:
            cmd += f" -s {setpoint}"
        if charge_setpoint is not None:
            cmd += f" -c {charge_setpoint}"
        if discharge_setpoint is not None:
            cmd += f" -d {discharge_setpoint}"
        if min_soc is not None:
            cmd += f" --min {min_soc}"
        if max_soc is not None:
            cmd += f" --max {max_soc}"
        return await self.send_console_command(cmd)

    async def set_full_solar_export(
        self,
        setpoint: int | None = None,
        min_soc: int | None = None,
        max_soc: int | None = None,
    ) -> dict[str, Any]:
        """Set battery to full solar export mode (export all solar production).

        Checks that the device is in local mode before sending the command.

        Args:
            setpoint: Optional power setpoint in watts
            min_soc: Optional minimum state of charge (%)
            max_soc: Optional maximum state of charge (%)

        Returns:
            Response dict with keys: command, output, exit_code

        Raises:
            HomevoltNotLocalModeError: If device is not in local mode
        """
        schedule = await self.get_schedule()
        if not schedule.get("local_mode", False):
            raise HomevoltNotLocalModeError(
                "Cannot set schedule: device is not in local mode. "
                "Enable local mode first to prevent remote overrides."
            )
        cmd = "sched_set 9"
        if setpoint is not None:
            cmd += f" -s {setpoint}"
        if min_soc is not None:
            cmd += f" --min {min_soc}"
        if max_soc is not None:
            cmd += f" --max {max_soc}"
        return await self.send_console_command(cmd)

    def _build_schedule_command(self, entry: dict[str, Any]) -> str:
        """Build a schedule command string from an entry dict.

        Args:
            entry: Dict with schedule entry parameters:
                - type: Control mode (0-9, required)
                - from_time: Start time (ISO 8601)
                - to_time: End time (ISO 8601)
                - min_soc: Minimum SOC constraint (0-100%)
                - max_soc: Maximum SOC constraint (0-100%)
                - setpoint: Power setpoint in watts
                - max_charge: Maximum charge power in watts
                - max_discharge: Maximum discharge power in watts
                - import_limit: Grid import limit in watts
                - export_limit: Grid export limit in watts

        Returns:
            Command string without the sched_set/sched_add prefix
        """
        parts = [str(entry["type"])]

        if "from_time" in entry:
            parts.append(f"--from {entry['from_time']}")
        if "to_time" in entry:
            parts.append(f"--to {entry['to_time']}")
        if "min_soc" in entry:
            parts.append(f"--min {entry['min_soc']}")
        if "max_soc" in entry:
            parts.append(f"--max {entry['max_soc']}")
        if "setpoint" in entry:
            parts.append(f"-s {entry['setpoint']}")
        if "max_charge" in entry:
            parts.append(f"-c {entry['max_charge']}")
        if "max_discharge" in entry:
            parts.append(f"-d {entry['max_discharge']}")
        if "import_limit" in entry:
            parts.append(f"-l {entry['import_limit']}")
        if "export_limit" in entry:
            parts.append(f"-x {entry['export_limit']}")

        return " ".join(parts)

    async def set_schedule(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Replace the current schedule with new entries.

        Checks that the device is in local mode before sending commands.
        Uses sched_set for the first entry (clears existing schedule),
        then sched_add for subsequent entries.

        Args:
            entries: List of schedule entry dicts. Each entry must have:
                - type: Control mode (0-9, required)
                And optionally:
                - from_time: Start time (ISO 8601)
                - to_time: End time (ISO 8601)
                - min_soc: Minimum SOC constraint (0-100%)
                - max_soc: Maximum SOC constraint (0-100%)
                - setpoint: Power setpoint in watts
                - max_charge: Maximum charge power in watts
                - max_discharge: Maximum discharge power in watts
                - import_limit: Grid import limit in watts
                - export_limit: Grid export limit in watts

        Returns:
            List of response dicts, one per entry

        Raises:
            HomevoltNotLocalModeError: If device is not in local mode
            ValueError: If entries list is empty
        """
        if not entries:
            raise ValueError("Schedule entries list cannot be empty")

        schedule = await self.get_schedule()
        if not schedule.get("local_mode", False):
            raise HomevoltNotLocalModeError(
                "Cannot set schedule: device is not in local mode. "
                "Enable local mode first to prevent remote overrides."
            )

        results = []
        for i, entry in enumerate(entries):
            cmd_args = self._build_schedule_command(entry)
            # First entry uses sched_set (clears existing), rest use sched_add
            prefix = "sched_set" if i == 0 else "sched_add"
            result = await self.send_console_command(f"{prefix} {cmd_args}")
            results.append(result)

        return results
