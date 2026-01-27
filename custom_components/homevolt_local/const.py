"""Constants for the Homevolt Local integration."""

from datetime import timedelta

DOMAIN = "homevolt_local"

# Configuration
CONF_HOST = "host"
CONF_PASSWORD = "password"
CONF_USERNAME = "username"

DEFAULT_USERNAME = "admin"
DEFAULT_SCAN_INTERVAL = 10  # seconds

# API Endpoints
ENDPOINT_STATUS = "/status.json"
ENDPOINT_EMS = "/ems.json"
ENDPOINT_NODES = "/nodes.json"
ENDPOINT_NODE_METRICS = "/node_metrics.json"  # Requires node_id parameter
ENDPOINT_CT = "/ct.json"  # Requires node_id parameter
ENDPOINT_MAINS = "/mains_data.json"
ENDPOINT_PARAMS = "/params.json"
ENDPOINT_SCHEDULE = "/schedule.json"
ENDPOINT_ERROR_REPORT = "/error_report.json"
ENDPOINT_OTA_MANIFEST = "/ota_manifest.json"
ENDPOINT_CONSOLE = "/console.json"

# Update interval
SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

# Device info
MANUFACTURER = "Tibber"
MODEL = "Homevolt Battery"
MODEL_CLUSTER = "Homevolt Battery Cluster"
