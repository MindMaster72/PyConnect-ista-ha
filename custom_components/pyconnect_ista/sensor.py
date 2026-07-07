"""Sensors for the ista Connect integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DATA_COORDINATOR, DOMAIN, MANUFACTURER, NAME
from .coordinator import PyConnectIstaDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class IstaSensorEntityDescription(SensorEntityDescription):
    """Describe an ista Connect sensor."""

    source: str
    consumption_type: str | None = None


LATEST_SENSOR_DESCRIPTIONS: tuple[IstaSensorEntityDescription, ...] = (
    IstaSensorEntityDescription(
        key="latest_heat",
        translation_key="latest_heat",
        source="latest",
        consumption_type="HEAT",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IstaSensorEntityDescription(
        key="latest_hot_water",
        translation_key="latest_hot_water",
        source="latest",
        consumption_type="HOT_WATER",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IstaSensorEntityDescription(
        key="latest_cold_water",
        translation_key="latest_cold_water",
        source="latest",
        consumption_type="COLD_WATER",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

SERIES_SENSOR_DESCRIPTIONS: tuple[IstaSensorEntityDescription, ...] = (
    IstaSensorEntityDescription(key="heat_month_points", translation_key="heat_month_points", source="heat_month"),
    IstaSensorEntityDescription(key="heat_day_points", translation_key="heat_day_points", source="heat_day"),
    IstaSensorEntityDescription(
        key="hot_water_month_points",
        translation_key="hot_water_month_points",
        source="hot_water_month",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
    ),
    IstaSensorEntityDescription(
        key="hot_water_day_points",
        translation_key="hot_water_day_points",
        source="hot_water_day",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
    ),
    IstaSensorEntityDescription(
        key="cold_water_month_points",
        translation_key="cold_water_month_points",
        source="cold_water_month",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
    ),
    IstaSensorEntityDescription(
        key="cold_water_day_points",
        translation_key="cold_water_day_points",
        source="cold_water_day",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ista Connect sensors."""
    coordinator: PyConnectIstaDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

    entities: list[SensorEntity] = [
        IstaLatestConsumptionSensor(coordinator, description) for description in LATEST_SENSOR_DESCRIPTIONS
    ]
    entities.extend(IstaSeriesSummarySensor(coordinator, description) for description in SERIES_SENSOR_DESCRIPTIONS)

    async_add_entities(entities)


class IstaBaseSensor(CoordinatorEntity[PyConnectIstaDataUpdateCoordinator], SensorEntity):
    """Base sensor for ista Connect."""

    entity_description: IstaSensorEntityDescription
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: PyConnectIstaDataUpdateCoordinator,
        description: IstaSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer=MANUFACTURER,
            name=NAME,
            model="istaConnect cloud account",
        )


class IstaLatestConsumptionSensor(IstaBaseSensor):
    """Latest consumption sensor."""

    @property
    def native_value(self) -> float | int | None:
        """Return the latest consumption value."""
        item = self._latest_item
        if not isinstance(item, dict):
            return None
        value = item.get("value")
        return value if isinstance(value, (float, int)) else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return native unit from the API when available."""
        item = self._latest_item
        if isinstance(item, dict) and isinstance(item.get("unit"), str):
            return item["unit"]
        return self.entity_description.native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra API attributes."""
        item = self._latest_item
        return item if isinstance(item, dict) else {}

    @property
    def _latest_item(self) -> dict[str, Any] | None:
        latest = self.coordinator.data.get("latest", {})
        value = latest.get(self.entity_description.consumption_type) if isinstance(latest, dict) else None
        if isinstance(value, list):
            return value[0] if value and isinstance(value[0], dict) else None
        return value if isinstance(value, dict) else None


class IstaSeriesSummarySensor(IstaBaseSensor):
    """Sensor showing the number of API values in a consumption series."""

    @property
    def native_value(self) -> int | None:
        """Return number of values available in the series."""
        values = self._series_values
        return len(values) if isinstance(values, list) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return summary attributes for the series."""
        series = self._series
        if not isinstance(series, dict):
            return {}
        return {
            "type": series.get("type"),
            "unit": series.get("unit"),
            "min": series.get("min"),
            "max": series.get("max"),
            "data_series_type": series.get("dataSeriesType"),
            "available_value_types": series.get("availableValueTypes"),
        }

    @property
    def _series(self) -> dict[str, Any] | None:
        series = self.coordinator.data.get("series", {})
        value = series.get(self.entity_description.source) if isinstance(series, dict) else None
        return value if isinstance(value, dict) else None

    @property
    def _series_values(self) -> list[Any] | None:
        series = self._series
        values = series.get("values") if isinstance(series, dict) else None
        return values if isinstance(values, list) else None
