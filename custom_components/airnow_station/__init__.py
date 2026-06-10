"""The AirNow Station integration."""

from __future__ import annotations

import logging
from collections.abc import Callable

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AirNowDataAPI
from .const import SUBENTRY_TYPE_STATION
from .coordinator import AirNowAccountConfigEntry, AirNowStationDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: AirNowAccountConfigEntry
) -> bool:
    """Set up an AirNow account entry and its station subentries.

    Station data outages are routine for AirNow, so one station failing
    its first refresh must not take down the account entry: each
    coordinator refreshes independently and a failure degrades only that
    station (it keeps polling and the entry reloads once it recovers).
    Only an account-wide auth failure — every station rejecting the key —
    fails setup, so reauth still fires.
    """
    client = AirNowDataAPI(
        entry.data[CONF_API_KEY], session=async_get_clientsession(hass)
    )

    coordinators: dict[str, AirNowStationDataUpdateCoordinator] = {}
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_STATION:
            continue
        coordinator = AirNowStationDataUpdateCoordinator(hass, entry, subentry, client)
        await coordinator.async_refresh()
        coordinators[subentry_id] = coordinator

    auth_failures = [
        coordinator.last_exception
        for coordinator in coordinators.values()
        if not coordinator.last_update_success
        and isinstance(coordinator.last_exception, ConfigEntryAuthFailed)
    ]
    if coordinators and len(auth_failures) == len(coordinators):
        # The shared key was rejected for every station: fail the whole
        # entry so Home Assistant starts the reauth flow.
        raise auth_failures[0]

    entry.runtime_data = coordinators
    _LOGGER.debug(
        "Account entry set up with %d station(s): %s",
        len(coordinators),
        [c.station_code for c in coordinators.values()],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Stations whose first refresh failed have no data to build sensors
    # from; keep them polling and reload the entry when data appears.
    for coordinator in coordinators.values():
        if coordinator.data:
            continue
        _LOGGER.warning(
            "Station %s (%s) has no recent data; its sensors will be created "
            "automatically when data resumes",
            coordinator.station_name,
            coordinator.station_code,
        )
        entry.async_on_unload(
            coordinator.async_add_listener(
                _make_recovery_listener(hass, entry, coordinator)
            )
        )

    # Reload on changes so newly added station subentries get set up.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


def _make_recovery_listener(
    hass: HomeAssistant,
    entry: AirNowAccountConfigEntry,
    coordinator: AirNowStationDataUpdateCoordinator,
) -> Callable[[], None]:
    """Build a coordinator listener that reloads the entry on recovery.

    Registering it also keeps the otherwise listener-less coordinator's
    refresh schedule alive.
    """

    @callback
    def _async_reload_on_recovery() -> None:
        if coordinator.last_update_success and coordinator.data:
            _LOGGER.info(
                "Station %s (%s) is reporting again; reloading to create its sensors",
                coordinator.station_name,
                coordinator.station_code,
            )
            hass.config_entries.async_schedule_reload(entry.entry_id)

    return _async_reload_on_recovery


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
