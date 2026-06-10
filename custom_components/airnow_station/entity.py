"""Base entity for the AirNow Station integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import AirNowStationDataUpdateCoordinator


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
