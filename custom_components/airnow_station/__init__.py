"""The AirNow Station integration."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AirNowDataAPI
from .const import SUBENTRY_TYPE_STATION
from .coordinator import AirNowAccountConfigEntry, AirNowStationDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: AirNowAccountConfigEntry
) -> bool:
    """Set up an AirNow account entry and its station subentries."""
    client = AirNowDataAPI(
        entry.data[CONF_API_KEY], session=async_get_clientsession(hass)
    )

    coordinators: dict[str, AirNowStationDataUpdateCoordinator] = {}
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_STATION:
            continue
        coordinator = AirNowStationDataUpdateCoordinator(
            hass, entry, subentry, client
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators[subentry_id] = coordinator

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload on changes so newly added station subentries get set up.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: AirNowAccountConfigEntry
) -> None:
    """Handle config entry updates (e.g. a subentry was added/removed)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: AirNowAccountConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
