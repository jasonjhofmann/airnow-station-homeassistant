"""Diagnostics support for the AirNow Station integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .coordinator import AirNowAccountConfigEntry

TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AirNowAccountConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the account entry and its stations.

    Station coordinates and AQS codes are public EPA monitor metadata,
    so only the API key needs redaction.
    """
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "stations": [
            {
                "title": entry.subentries[subentry_id].title,
                "subentry": dict(entry.subentries[subentry_id].data),
                "update_interval": str(coordinator.update_interval),
                "last_update_success": coordinator.last_update_success,
                "last_exception": (
                    str(coordinator.last_exception)
                    if coordinator.last_exception
                    else None
                ),
                "data": coordinator.data,
            }
            for subentry_id, coordinator in entry.runtime_data.items()
        ],
    }
