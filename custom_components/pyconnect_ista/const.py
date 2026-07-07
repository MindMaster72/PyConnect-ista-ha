"""Constants for the ista Connect integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "pyconnect_ista"
MANUFACTURER = "ista"
NAME = "ista Connect"

CONF_UPDATE_INTERVAL = "update_interval"
DEFAULT_UPDATE_INTERVAL = 24
DEFAULT_SCAN_INTERVAL = timedelta(hours=DEFAULT_UPDATE_INTERVAL)

DATA_COORDINATOR = "coordinator"
ATTRIBUTION = "Data provided by istaConnect"
