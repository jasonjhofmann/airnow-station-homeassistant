"""Diagnostics support for the AirNow Station integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .coordinator import AirNowAccountConfigEntry

# Keys redacted at any depth. Station latitude/longitude and AQS codes are
# deliberately NOT redacted: they are public EPA monitor metadata, and the
# dump never contains the user's own coordinates (search input is not
# stored). "API_KEY" is the raw AirNow query-parameter casing — never in
# today's dump, but pre-listed so request params/URLs attached by a future
# revision would scrub automatically. Unused keys cost nothing.
TO_REDACT = {CONF_API_KEY, "API_KEY"}


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
