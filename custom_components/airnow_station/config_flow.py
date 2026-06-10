"""Config flow for the AirNow Station integration.

One account-level config entry holds the API key; each monitored station
is a config subentry of type ``station`` (unique ID = full AQS code).
"""

from __future__ import annotations

from datetime import timedelta
import logging
import math
from typing import Any

from aiohttp.client_exceptions import ClientConnectorError
from pyairnow.errors import (
    AirNowError,
    EmptyResponseError,
    InvalidJsonError,
    InvalidKeyError,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import dt as dt_util

from .api import AirNowDataAPI
from .const import (
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    DISCOVERY_BBOX_DEG,
    DOMAIN,
    LOOKBACK_HOURS,
    SUBENTRY_TYPE_STATION,
)

_LOGGER = logging.getLogger(__name__)

# Documentation URL for API key generation
_API_KEY_URL = "https://docs.airnowapi.org/account/request/"

CONF_STATION = "station"


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometers."""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    a = (
        math.sin((rlat2 - rlat1) / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin((rlon2 - rlon1) / 2) ** 2
    )
    return 2 * 6371.0 * math.asin(math.sqrt(a))


async def _async_discover_stations(
    hass: HomeAssistant, api_key: str, latitude: float, longitude: float
) -> dict[str, dict[str, Any]]:
    """Find monitoring stations reporting data near the coordinates."""
    client = AirNowDataAPI(api_key, session=async_get_clientsession(hass))

    end = dt_util.utcnow()
    rows = await client.data.bbox(
        longitude - DISCOVERY_BBOX_DEG,
        latitude - DISCOVERY_BBOX_DEG,
        longitude + DISCOVERY_BBOX_DEG,
        latitude + DISCOVERY_BBOX_DEG,
        start_date=end - timedelta(hours=LOOKBACK_HOURS),
        end_date=end,
    )

    stations: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = row.get("FullAQSCode")
        if not code or code in stations:
            continue
        stations[code] = {
            CONF_STATION_CODE: code,
            CONF_STATION_NAME: row["SiteName"],
            CONF_LATITUDE: row["Latitude"],
            CONF_LONGITUDE: row["Longitude"],
            "distance": _distance_km(
                latitude, longitude, row["Latitude"], row["Longitude"]
            ),
        }
    return dict(sorted(stations.items(), key=lambda item: item[1]["distance"]))


async def _async_validate_key(hass: HomeAssistant, api_key: str) -> None:
    """Validate the API key; raise on auth/connection problems.

    An empty result is fine — it proves the key was accepted.
    """
    try:
        await _async_discover_stations(
            hass, api_key, hass.config.latitude, hass.config.longitude
        )
    except EmptyResponseError:
        pass


class AirNowStationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the account-level config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: the API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            self._async_abort_entries_match({CONF_API_KEY: api_key})
            try:
                await _async_validate_key(self.hass, api_key)
            except InvalidKeyError:
                errors["base"] = "invalid_auth"
            except (AirNowError, InvalidJsonError, ClientConnectorError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="AirNow", data={CONF_API_KEY: api_key}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            description_placeholders={"api_key_url": _API_KEY_URL},
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication on an invalid API key."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key and validate it."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            try:
                await _async_validate_key(self.hass, api_key)
            except InvalidKeyError:
                errors["base"] = "invalid_auth"
            except (AirNowError, InvalidJsonError, ClientConnectorError):
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            description_placeholders={"api_key_url": _API_KEY_URL},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow changing the API key proactively."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            try:
                await _async_validate_key(self.hass, api_key)
            except InvalidKeyError:
                errors["base"] = "invalid_auth"
            except (AirNowError, InvalidJsonError, ClientConnectorError):
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates={CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            description_placeholders={"api_key_url": _API_KEY_URL},
            errors=errors,
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_STATION: StationSubentryFlowHandler}


class StationSubentryFlowHandler(ConfigSubentryFlow):
    """Flow for adding a monitoring station to an account entry."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        super().__init__()
        self._stations: dict[str, dict[str, Any]] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the search step: coordinates to look around."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = self._get_entry().data[CONF_API_KEY]
            try:
                self._stations = await _async_discover_stations(
                    self.hass,
                    api_key,
                    user_input[CONF_LATITUDE],
                    user_input[CONF_LONGITUDE],
                )
            except InvalidKeyError:
                errors["base"] = "invalid_auth"
            except EmptyResponseError:
                errors["base"] = "no_stations"
            except (AirNowError, InvalidJsonError, ClientConnectorError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if not self._stations:
                    errors["base"] = "no_stations"
                else:
                    return await self.async_step_station()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LATITUDE, default=self.hass.config.latitude
                    ): cv.latitude,
                    vol.Required(
                        CONF_LONGITUDE, default=self.hass.config.longitude
                    ): cv.longitude,
                }
            ),
            errors=errors,
        )

    async def async_step_station(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Let the user pick one of the discovered stations."""
        if user_input is not None:
            station = self._stations[user_input[CONF_STATION]]
            return self.async_create_entry(
                title=station[CONF_STATION_NAME],
                data={
                    CONF_STATION_CODE: station[CONF_STATION_CODE],
                    CONF_STATION_NAME: station[CONF_STATION_NAME],
                    CONF_LATITUDE: station[CONF_LATITUDE],
                    CONF_LONGITUDE: station[CONF_LONGITUDE],
                },
                unique_id=station[CONF_STATION_CODE],
            )

        options = [
            SelectOptionDict(
                value=code,
                label=f"{info[CONF_STATION_NAME]} ({info['distance']:.1f} km)",
            )
            for code, info in self._stations.items()
        ]
        return self.async_show_form(
            step_id="station",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATION): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.LIST
                        )
                    )
                }
            ),
        )
