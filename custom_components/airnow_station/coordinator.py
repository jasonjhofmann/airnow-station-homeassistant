"""DataUpdateCoordinator for the AirNow Station integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from aiohttp.client_exceptions import ClientConnectorError
from pyairnow.errors import (
    AirNowError,
    EmptyResponseError,
    InvalidJsonError,
    InvalidKeyError,
)

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import AirNowDataAPI, latest_by_parameter
from .const import (
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LOOKBACK_HOURS,
    STATION_BBOX_DEG,
)

_LOGGER = logging.getLogger(__name__)

type AirNowAccountConfigEntry = ConfigEntry[
    dict[str, AirNowStationDataUpdateCoordinator]
]


class AirNowStationDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, dict[str, Any]]]
):
    """Poll the /aq/data/ endpoint for a single station subentry."""

    config_entry: AirNowAccountConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AirNowAccountConfigEntry,
        subentry: ConfigSubentry,
        client: AirNowDataAPI,
    ) -> None:
        """Initialize."""
        data = subentry.data
        self.subentry = subentry
        self.station_code: str = data[CONF_STATION_CODE]
        self.station_name: str = data[CONF_STATION_NAME]
        self.latitude: float = data[CONF_LATITUDE]
        self.longitude: float = data[CONF_LONGITUDE]
        self.api = client

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} {self.station_name}",
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch the latest observation per parameter for the station."""
        end = dt_util.utcnow()
        start = end - timedelta(hours=LOOKBACK_HOURS)

        try:
            rows = await self.api.data.bbox(
                self.longitude - STATION_BBOX_DEG,
                self.latitude - STATION_BBOX_DEG,
                self.longitude + STATION_BBOX_DEG,
                self.latitude + STATION_BBOX_DEG,
                start_date=start,
                end_date=end,
                include_raw_concentrations=True,
            )
        except InvalidKeyError as err:
            raise ConfigEntryAuthFailed("Invalid AirNow API key") from err
        except EmptyResponseError as err:
            raise UpdateFailed(
                f"No data returned for station {self.station_name}"
            ) from err
        except (AirNowError, InvalidJsonError, ClientConnectorError) as err:
            raise UpdateFailed(err) from err

        rows = [row for row in rows if row.get("FullAQSCode") == self.station_code]
        data = latest_by_parameter(rows)
        if not data:
            raise UpdateFailed(
                f"No recent observations for station {self.station_name}"
            )
        return data
