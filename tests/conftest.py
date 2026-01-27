"""Fixtures for Homevolt Local tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.homevolt_local.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_homevolt_api() -> Generator[AsyncMock]:
    """Mock HomevoltApi."""
    with patch(
        "custom_components.homevolt_local.config_flow.HomevoltApi",
        autospec=True,
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.test_connection = AsyncMock(return_value={"status": "ok"})
        mock_api.get_ems = AsyncMock(
            return_value={
                "ems": [{"ecu_id": "test123"}],
            }
        )
        mock_api.close = AsyncMock()
        yield mock_api


@pytest.fixture
def mock_config_data() -> dict:
    """Return mock config data."""
    return {
        CONF_HOST: "homevolt-test.local",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "testpass",
    }


@pytest.fixture
def mock_config_data_no_auth() -> dict:
    """Return mock config data without auth."""
    return {
        CONF_HOST: "homevolt-test.local",
    }


@pytest.fixture
def mock_ems_data() -> dict:
    """Return mock EMS data in nested format (leader - has multiple units)."""
    return {
        "ems": [
            {
                "ecu_id": "test123",
                "op_state_str": "IDLE",
                "ems_data": {
                    "soc_avg": 7500,  # centi-percent (75%)
                    "power": 1500,
                    "frequency": 50000,  # milli-Hz
                    "sys_temp": 250,  # deci-degrees
                    "avail_cap": 5000,
                    "energy_produced": 10000000,  # Wh
                    "energy_consumed": 8000000,  # Wh
                    "state_str": "discharging",
                },
                "ems_info": {
                    "capacity": 10000,  # Wh
                    "rated_power": 2500,  # W
                },
                "ems_prediction": {
                    "avail_ch_pwr": 5000,
                    "avail_di_pwr": 4500,
                    "avail_ch_energy": 10000,
                    "avail_di_energy": 8000,
                    "avail_inv_ch_pwr": 4800,
                    "avail_inv_di_pwr": 4300,
                },
                "bms_data": [
                    {
                        "soc": 75,
                        "voltage": 48.5,
                        "current": 30.5,
                    }
                ],
            },
            {
                "ecu_id": "follower1",
                "op_state_str": "IDLE",
                "ems_data": {
                    "soc_avg": 7600,
                    "power": 1600,
                    "frequency": 50000,
                    "state_str": "discharging",
                },
                "ems_info": {
                    "capacity": 10000,  # Wh
                    "rated_power": 2500,  # W
                },
                "ems_prediction": {
                    "avail_ch_pwr": 5000,
                    "avail_di_pwr": 4500,
                    "avail_ch_energy": 10000,
                    "avail_di_energy": 8000,
                    "avail_inv_ch_pwr": 4800,
                    "avail_inv_di_pwr": 4300,
                },
            },
        ],
        "aggregated": {
            "ems_info": {
                "capacity": 20000,  # Wh
                "rated_power": 5000,  # W
            },
            "ems_data": {
                "soc_avg": 7550,  # centi-percent (75.5%)
                "power": 3100,  # W (aggregated from both units)
                "frequency": 50000,  # milli-Hz
                "energy_produced": 18000000,  # Wh
                "energy_consumed": 16000000,  # Wh
                "avail_cap": 10000,  # Wh
                "state_str": "discharging",
            },
            "ems_prediction": {
                "avail_ch_pwr": 10000,
                "avail_di_pwr": 9000,
                "avail_ch_energy": 20000,
                "avail_di_energy": 16000,
                "avail_inv_ch_pwr": 9600,
                "avail_inv_di_pwr": 8600,
            },
            "op_state_str": "IDLE",
        },
    }


@pytest.fixture
def mock_mains_data() -> dict:
    """Return mock mains data."""
    return {
        "mains_voltage_rms": 230.5,
        "frequency": 50.01,
    }


@pytest.fixture
def mock_status_data() -> dict:
    """Return mock status data."""
    return {
        "up_time": 123456789,
        "firmware": {
            "esp": "1.2.3",
        },
    }


@pytest.fixture
def mock_params_data() -> list:
    """Return mock params data."""
    return [
        {"name": "ecu_mdns_instance_name", "value": "My Homevolt"},
        {"name": "settings_local", "value": [True]},
        {"name": "ecu_main_fuse_size_a", "value": [25]},
        {"name": "ecu_group_fuse_size_a", "value": [16]},
        {"name": "other_param", "value": "some_value"},
    ]


@pytest.fixture
def mock_ems_data_leader() -> dict:
    """Return mock EMS data for a leader device (has multiple units in ems list)."""
    return {
        "ems": [
            {
                "ecu_id": "test123",
                "op_state_str": "IDLE",
                "ems_data": {
                    "soc_avg": 7500,
                    "power": 1500,
                    "frequency": 50000,
                },
                "ems_info": {
                    "capacity": 10000,
                    "rated_power": 2500,
                },
                "ems_prediction": {
                    "avail_ch_pwr": 5000,
                    "avail_di_pwr": 4500,
                    "avail_ch_energy": 10000,
                    "avail_di_energy": 8000,
                    "avail_inv_ch_pwr": 4800,
                    "avail_inv_di_pwr": 4300,
                },
            },
            {
                "ecu_id": "follower1",
                "op_state_str": "IDLE",
                "ems_data": {
                    "soc_avg": 7600,
                    "power": 1500,
                    "frequency": 50000,
                },
                "ems_info": {
                    "capacity": 10000,
                    "rated_power": 2500,
                },
                "ems_prediction": {
                    "avail_ch_pwr": 5000,
                    "avail_di_pwr": 4500,
                    "avail_ch_energy": 10000,
                    "avail_di_energy": 8000,
                    "avail_inv_ch_pwr": 4800,
                    "avail_inv_di_pwr": 4300,
                },
            },
        ],
        "aggregated": {
            "ems_info": {
                "capacity": 20000,
                "rated_power": 5000,
            },
            "ems_data": {
                "soc_avg": 7550,
                "power": 3100,
                "frequency": 50000,
                "energy_produced": 18000000,
                "energy_consumed": 16000000,
                "avail_cap": 10000,
                "state_str": "discharging",
            },
            "ems_prediction": {
                "avail_ch_pwr": 10000,
                "avail_di_pwr": 9000,
                "avail_ch_energy": 20000,
                "avail_di_energy": 16000,
                "avail_inv_ch_pwr": 9600,
                "avail_inv_di_pwr": 8600,
            },
            "op_state_str": "IDLE",
        },
    }


@pytest.fixture
def mock_ems_data_follower() -> dict:
    """Return mock EMS data for a follower/standalone device (single unit in ems list)."""
    return {
        "ems": [
            {
                "ecu_id": "test123",
                "op_state_str": "IDLE",
                "ems_data": {
                    "soc_avg": 7500,
                    "power": 1500,
                    "frequency": 50000,
                },
                "ems_info": {
                    "capacity": 10000,
                    "rated_power": 2500,
                },
            }
        ],
    }


@pytest.fixture
def mock_nodes_data() -> dict:
    """Return mock nodes data."""
    return {
        "nodes": [
            {"id": 1, "type": "battery"},
        ]
    }


@pytest.fixture
def mock_schedule_data() -> dict:
    """Return mock schedule data."""
    return {
        "local_mode": True,
        "schedule_id": "test-schedule-123",
        "schedule": [{"id": 1, "from": 1766131200, "to": 1766132100, "type": 1, "params": {}}],
    }


@pytest.fixture
def mock_all_data(
    mock_ems_data: dict,
    mock_mains_data: dict,
    mock_status_data: dict,
    mock_params_data: list,
    mock_nodes_data: dict,
    mock_schedule_data: dict,
) -> dict:
    """Return mock all data combined."""
    return {
        "ems": mock_ems_data,
        "mains": mock_mains_data,
        "status": mock_status_data,
        "params": mock_params_data,
        "nodes": mock_nodes_data,
        "schedule": mock_schedule_data,
    }


@pytest.fixture
def mock_coordinator_data(
    mock_ems_data: dict,
    mock_mains_data: dict,
    mock_status_data: dict,
    mock_params_data: list,
    mock_schedule_data: dict,
) -> dict:
    """Return mock coordinator data (what get_all_data returns)."""
    return {
        "ems": mock_ems_data,
        "mains": mock_mains_data,
        "status": mock_status_data,
        "params": mock_params_data,
        "nodes": {},
        "schedule": mock_schedule_data,
    }
