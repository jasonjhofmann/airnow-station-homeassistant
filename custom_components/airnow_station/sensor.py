"""Sensors for the AirNow Station integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import MISSING_VALUE
from .const import AQI_CATEGORIES, ATTRIBUTION, DOMAIN
from .coordinator import AirNowAccountConfigEntry, AirNowStationDataUpdateCoordinator

PARALLEL_UPDATES = 0

ATTR_OBSERVED_UTC = "observed_utc"
ATTR_RAW_CONCENTRATION = "raw_concentration"
ATTR_DOMINANT_POLLUTANT = "dominant_pollutant"
ATTR_CATEGORY = "category"

# Concentration sensors, keyed by the *response* parameter name. Ozone, NO2,
# and SO2 are reported in ppb, which the matching HA device classes do not
# accept (they require µg/m³), so those go without a device class.
CONCENTRATION_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    "PM2.5": SensorEntityDescription(
        key="pm25",
        translation_key="pm25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "PM10": SensorEntityDescription(
        key="pm10",
        translation_key="pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "OZONE": SensorEntityDescription(
        key="ozone",
        translation_key="ozone",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "NO2": SensorEntityDescription(
        key="no2",
        translation_key="no2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "SO2": SensorEntityDescription(
        key="so2",
        translation_key="so2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "CO": SensorEntityDescription(
        key="co",
        translation_key="co",
        device_class=SensorDeviceClass.CO,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}

AQI_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    param: SensorEntityDescription(
        key=f"{description.key}_aqi",
        translation_key=f"{description.key}_aqi",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    )
    for param, description in CONCENTRATION_DESCRIPTIONS.items()
}

OVERALL_AQI_DESCRIPTION = SensorEntityDescription(
    key="aqi",
    translation_key="aqi",
    device_class=SensorDeviceClass.AQI,
    state_class=SensorStateClass.MEASUREMENT,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AirNowAccountConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for each station subentry's reported parameters."""
    for subentry_id, coordinator in config_entry.runtime_data.items():
        entities: list[SensorEntity] = [
            AirNowStationOverallAqiSensor(coordinator)
        ]
        for param in coordinator.data:
            if param not in CONCENTRATION_DESCRIPTIONS:
                continue
            entities.append(AirNowStationConcentrationSensor(coordinator, param))
            entities.append(AirNowStationAqiSensor(coordinator, param))

        async_add_entities(entities, config_subentry_id=subentry_id)


class AirNowStationEntity(
    CoordinatorEntity[AirNowStationDataUpdateCoordinator], SensorEntity
):
    """Base entity for a monitoring station."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: AirNowStationDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        first_row = next(iter(coordinator.data.values()))
        agency = (first_row.get("AgencyName") or "").strip() or None
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.station_code)},
            manufacturer="AirNow",
            model=agency,
            name=coordinator.station_name,
            configuration_url="https://www.airnow.gov/",
        )


class AirNowStationParameterSensor(AirNowStationEntity):
    """Base for sensors bound to a single parameter."""

    def __init__(
        self,
        coordinator: AirNowStationDataUpdateCoordinator,
        param: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.param = param
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.station_code}-{description.key}"

    @property
    def available(self) -> bool:
        """Stay unavailable while the parameter is missing from the feed."""
        return super().available and self.param in self.coordinator.data


class AirNowStationConcentrationSensor(AirNowStationParameterSensor):
    """Measured pollutant concentration."""

    def __init__(
        self, coordinator: AirNowStationDataUpdateCoordinator, param: str
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, param, CONCENTRATION_DESCRIPTIONS[param])

    @property
    def native_value(self) -> StateType:
        """Return the concentration."""
        row = self.coordinator.data.get(self.param)
        return row["Value"] if row else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return observation time and raw concentration."""
        if (row := self.coordinator.data.get(self.param)) is None:
            return None
        attrs: dict[str, Any] = {ATTR_OBSERVED_UTC: row["UTC"]}
        raw = row.get("RawConcentration", MISSING_VALUE)
        if raw != MISSING_VALUE:
            attrs[ATTR_RAW_CONCENTRATION] = raw
        return attrs


class AirNowStationAqiSensor(AirNowStationParameterSensor):
    """Per-pollutant AQI."""

    def __init__(
        self, coordinator: AirNowStationDataUpdateCoordinator, param: str
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, param, AQI_DESCRIPTIONS[param])

    @property
    def native_value(self) -> StateType:
        """Return the AQI, if AirNow computed one (CO often reports -999)."""
        row = self.coordinator.data.get(self.param)
        if row is None or row["AQI"] < 0:
            return None
        return row["AQI"]


class AirNowStationOverallAqiSensor(AirNowStationEntity):
    """Overall AQI: the maximum across all reported pollutants."""

    def __init__(self, coordinator: AirNowStationDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = OVERALL_AQI_DESCRIPTION
        self._attr_unique_id = f"{coordinator.station_code}-aqi"

    def _dominant_row(self) -> tuple[str, dict[str, Any]] | None:
        rows = [
            item for item in self.coordinator.data.items() if item[1]["AQI"] >= 0
        ]
        if not rows:
            return None
        return max(rows, key=lambda item: item[1]["AQI"])

    @property
    def native_value(self) -> StateType:
        """Return the maximum per-pollutant AQI."""
        if (dominant := self._dominant_row()) is None:
            return None
        return dominant[1]["AQI"]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the dominant pollutant and AQI category."""
        if (dominant := self._dominant_row()) is None:
            return None
        param, row = dominant
        return {
            ATTR_DOMINANT_POLLUTANT: param,
            ATTR_CATEGORY: AQI_CATEGORIES.get(row.get("Category")),
            ATTR_OBSERVED_UTC: row["UTC"],
        }
