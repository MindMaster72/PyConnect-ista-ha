"""Diagnostics for the ista Connect integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_COORDINATOR, DOMAIN


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    data = coordinator.data or {}
    user = data.get("user") if isinstance(data, dict) else None

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "options": dict(entry.options),
        },
        "user": {
            "has_user": isinstance(user, dict),
            "keys": sorted(user.keys()) if isinstance(user, dict) else [],
        },
        "latest_keys": sorted(data.get("latest", {}).keys()) if isinstance(data.get("latest"), dict) else [],
        "series_keys": sorted(data.get("series", {}).keys()) if isinstance(data.get("series"), dict) else [],
    }
