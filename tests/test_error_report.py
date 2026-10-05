"""Tests for the /error_report.json problem count (API, coordinator, sensor)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.homevolt_local.api import (
    HomevoltApi,
    HomevoltApiError,
    HomevoltAuthError,
    HomevoltRateLimitError,
)
from custom_components.homevolt_local.coordinator import HomevoltErrorReportCoordinator
from custom_components.homevolt_local.sensor import HomevoltErrorReportSensor

from .test_api import AsyncContextManager


def _entry(status: str, name: str = "check", sub: str = "SUB", message: str = "") -> dict:
    return {
        "sub_system_id": 0,
        "sub_system_name": sub,
        "error_id": 1,
        "error_name": name,
        "activated": status,
        "message": message,
        "details": [],
    }


REPORT = [
    _entry("ok", "power_24v", "ECU"),
    _entry("error", "lte", "CONNECTIVITY", "LTE error: 5"),
    _entry("warning", "calibration status", "PULSE SOLAR", "Line diff invalid"),
    _entry("unknown", "distribute status", "PULSE SOLAR"),
]


class TestApiGetErrorReport:
    """get_error_report handles the bare-array payload without caching."""

    @pytest.fixture
    def api(self) -> HomevoltApi:
        return HomevoltApi("homevolt.local", None, None, MagicMock())

    def _respond(self, api: HomevoltApi, payload: object) -> None:
        response = AsyncMock()
        response.status = 200
        response.json = AsyncMock(return_value=payload)
        response.raise_for_status = MagicMock()
        api._session.get = MagicMock(return_value=AsyncContextManager(response))

    async def test_returns_list(self, api: HomevoltApi) -> None:
        self._respond(api, REPORT)
        assert await api.get_error_report() == REPORT

    async def test_non_list_payload_raises(self, api: HomevoltApi) -> None:
        self._respond(api, {"not": "a list"})
        with pytest.raises(HomevoltApiError):
            await api.get_error_report()

    async def test_not_served_from_stale_cache(self, api: HomevoltApi) -> None:
        """A successful response must not be replayed after the device stops answering."""
        self._respond(api, REPORT)
        await api.get_error_report()
        api._session.get = MagicMock(side_effect=HomevoltApiError("down"))
        with pytest.raises(HomevoltApiError):
            await api.get_error_report()

    async def test_not_in_get_all_data(self, api: HomevoltApi) -> None:
        self._respond(api, {})
        assert "error_report" not in await api.get_all_data()


class TestErrorReportCoordinator:
    """The coordinator keeps only error/warning entries."""

    @pytest.fixture
    def mock_api(self) -> MagicMock:
        api = MagicMock()
        api.get_error_report = AsyncMock(return_value=REPORT)
        return api

    @pytest.fixture
    def coordinator(
        self, hass: HomeAssistant, mock_api: MagicMock
    ) -> HomevoltErrorReportCoordinator:
        return HomevoltErrorReportCoordinator(hass, mock_api, "homevolt.local")

    async def test_filters_to_problems(self, coordinator: HomevoltErrorReportCoordinator) -> None:
        assert await coordinator._async_update_data() == [
            {
                "subsystem": "CONNECTIVITY",
                "check": "lte",
                "status": "error",
                "message": "LTE error: 5",
            },
            {
                "subsystem": "PULSE SOLAR",
                "check": "calibration status",
                "status": "warning",
                "message": "Line diff invalid",
            },
        ]

    async def test_all_ok_is_empty(
        self, coordinator: HomevoltErrorReportCoordinator, mock_api: MagicMock
    ) -> None:
        mock_api.get_error_report.return_value = [_entry("ok"), _entry("unknown")]
        assert await coordinator._async_update_data() == []

    async def test_skips_non_dict_entries(
        self, coordinator: HomevoltErrorReportCoordinator, mock_api: MagicMock
    ) -> None:
        mock_api.get_error_report.return_value = ["junk", _entry("error")]
        assert len(await coordinator._async_update_data()) == 1

    async def test_api_error_is_update_failed(
        self, coordinator: HomevoltErrorReportCoordinator, mock_api: MagicMock
    ) -> None:
        mock_api.get_error_report.side_effect = HomevoltApiError("boom")
        with pytest.raises(UpdateFailed) as exc:
            await coordinator._async_update_data()
        assert exc.value.translation_key == "cannot_connect"

    @pytest.mark.parametrize(
        ("error", "key"),
        [
            (HomevoltAuthError("401"), "invalid_auth"),
            (HomevoltRateLimitError("429"), "rate_limited"),
        ],
    )
    async def test_auth_errors_trigger_reauth(
        self,
        coordinator: HomevoltErrorReportCoordinator,
        mock_api: MagicMock,
        error: Exception,
        key: str,
    ) -> None:
        mock_api.get_error_report.side_effect = error
        with pytest.raises(ConfigEntryAuthFailed) as exc:
            await coordinator._async_update_data()
        assert exc.value.translation_key == key


class TestErrorReportSensor:
    """The sensor reports the count and lists the problems."""

    def _sensor(self, data: list[dict] | None, success: bool = True) -> HomevoltErrorReportSensor:
        main = MagicMock()
        main.device_id = "ecu1"
        main.device_name = "Homevolt"
        main.firmware_version = "1"
        main.host = "homevolt.local"
        coordinator = MagicMock()
        coordinator.data = data
        coordinator.last_update_success = success
        return HomevoltErrorReportSensor(main, coordinator)

    def test_metadata(self) -> None:
        sensor = self._sensor([])
        assert sensor.unique_id == "ecu1_error_report_problems"
        assert sensor.translation_key == "error_report_problems"
        assert sensor.entity_category is EntityCategory.DIAGNOSTIC
        assert sensor.state_class is SensorStateClass.MEASUREMENT

    def test_count_and_attributes(self) -> None:
        problems = [
            {"subsystem": "A", "check": "x", "status": "error", "message": ""},
            {"subsystem": "B", "check": "y", "status": "warning", "message": ""},
            {"subsystem": "C", "check": "z", "status": "error", "message": ""},
        ]
        sensor = self._sensor(problems)
        assert sensor.native_value == 3
        assert sensor.extra_state_attributes == {"problems": problems, "errors": 2, "warnings": 1}

    def test_zero_problems(self) -> None:
        assert self._sensor([]).native_value == 0

    def test_unavailable_without_data(self) -> None:
        sensor = self._sensor(None, success=False)
        assert sensor.native_value is None
        assert sensor.extra_state_attributes is None
        assert sensor.available is False
