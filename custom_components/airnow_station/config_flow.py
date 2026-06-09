"""Config flow for the AirNow Station integration."""

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

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
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
    STATION_BBOX_DEG,
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


class AirNowStationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AirNow Station."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._api_key: str | None = None
        self._stations: dict[str, dict[str, Any]] = {}

    async def _async_discover_stations(
        self, api_key: str, latitude: float, longitude: float
    ) -> dict[str, dict[str, Any]]:
        """Find monitoring stations reporting data near the coordinates."""
        session = async_get_clientsession(self.hass)
        client = AirNowDataAPI(api_key, session=session)

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
        return dict(
            sorted(stations.items(), key=lambda item: item[1]["distance"])
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: API key + search coordinates."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._stations = await self._async_discover_stations(
                    user_input[CONF_API_KEY],
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
                    self._api_key = user_input[CONF_API_KEY]
                    return await self.async_step_station()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(
                        CONF_LATITUDE, default=self.hass.config.latitude
                    ): cv.latitude,
                    vol.Required(
                        CONF_LONGITUDE, default=self.hass.config.longitude
                    ): cv.longitude,
                }
            ),
            description_placeholders={"api_key_url": _API_KEY_URL},
            errors=errors,
        )

    async def async_step_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick one of the discovered stations."""
        if user_input is not None:
            station = self._stations[user_input[CONF_STATION]]

            await self.async_set_unique_id(station[CONF_STATION_CODE])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=station[CONF_STATION_NAME],
                data={
                    CONF_API_KEY: self._api_key,
                    CONF_STATION_CODE: station[CONF_STATION_CODE],
                    CONF_STATION_NAME: station[CONF_STATION_NAME],
                    CONF_LATITUDE: station[CONF_LATITUDE],
                    CONF_LONGITUDE: station[CONF_LONGITUDE],
                },
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
            entry = self._get_reauth_entry()
            session = async_get_clientsession(self.hass)
            client = AirNowDataAPI(user_input[CONF_API_KEY], session=session)
            end = dt_util.utcnow()
            try:
                await client.data.bbox(
                    entry.data[CONF_LONGITUDE] - STATION_BBOX_DEG,
                    entry.data[CONF_LATITUDE] - STATION_BBOX_DEG,
                    entry.data[CONF_LONGITUDE] + STATION_BBOX_DEG,
                    entry.data[CONF_LATITUDE] + STATION_BBOX_DEG,
                    start_date=end - timedelta(hours=LOOKBACK_HOURS),
                    end_date=end,
                )
            except InvalidKeyError:
                errors["base"] = "invalid_auth"
            except EmptyResponseError:
                # Key accepted; the station just has no rows right now.
                pass
            except (AirNowError, InvalidJsonError, ClientConnectorError):
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            description_placeholders={"api_key_url": _API_KEY_URL},
            errors=errors,
        )
