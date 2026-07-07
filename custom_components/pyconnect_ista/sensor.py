"""Sensors for the ista Connect integration."""

from __future__ import annotations

from collections.abc import Mapping
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


SENSOR_DESCRIPTIONS: tuple[IstaSensorEntityDescription, ...] = (
    IstaSensorEntityDescription(
        key="latest_heat",
        name="Ogrzewanie - ostatni odczyt",
        source="latest",
        consumption_type="HEAT",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IstaSensorEntityDescription(
        key="latest_hot_water",
        name="Ciepla woda - ostatni odczyt",
        source="latest",
        consumption_type="HOT_WATER",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IstaSensorEntityDescription(
        key="latest_cold_water",
        name="Zimna woda - ostatni odczyt",
        source="latest",
        consumption_type="COLD_WATER",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IstaSensorEntityDescription(
        key="heat_month_points",
        name="Ogrzewanie - miesiac",
        source="heat_month",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IstaSensorEntityDescription(
        key="heat_day_points",
        name="Ogrzewanie - dzien",
        source="heat_day",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IstaSensorEntityDescription(
        key="hot_water_month_points",
        name="Ciepla woda - miesiac",
        source="hot_water_month",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IstaSensorEntityDescription(
        key="hot_water_day_points",
        name="Ciepla woda - dzien",
        source="hot_water_day",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IstaSensorEntityDescription(
        key="cold_water_month_points",
        name="Zimna woda - miesiac",
        source="cold_water_month",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IstaSensorEntityDescription(
        key="cold_water_day_points",
        name="Zimna woda - dzien",
        source="cold_water_day",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ista Connect sensors."""
    coordinator: PyConnectIstaDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    async_add_entities([IstaConsumptionSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS])


class IstaConsumptionSensor(CoordinatorEntity[PyConnectIstaDataUpdateCoordinator], SensorEntity):
    """Consumption sensor for ista Connect."""

    entity_description: IstaSensorEntityDescription
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

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

    @property
    def native_value(self) -> float | int | None:
        """Return the latest numeric value for this sensor."""
        point = self._point
        value = point.get("value") if point else None
        return value if isinstance(value, (float, int)) else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return native unit from the API when available."""
        point = self._point
        unit = point.get("unit") if point else None
        if isinstance(unit, str):
            return _normalize_unit(unit)
        return self.entity_description.native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return useful API attributes."""
        point = self._point
        if not point:
            return {}

        attrs: dict[str, Any] = {
            "date": point.get("date"),
            "unit": point.get("unit"),
            "source": self.entity_description.source,
        }

        if value_type := point.get("valueType"):
            attrs["value_type"] = value_type
        if count := point.get("values_count"):
            attrs["values_count"] = count
        if data_series_type := point.get("dataSeriesType"):
            attrs["data_series_type"] = data_series_type

        return attrs

    @property
    def _point(self) -> dict[str, Any] | None:
        if self.entity_description.source == "latest":
            return self._latest_point()
        return self._series_point()

    def _latest_point(self) -> dict[str, Any] | None:
        latest = self.coordinator.data.get("latest", {})
        if not isinstance(latest, dict) or self.entity_description.consumption_type is None:
            return None

        items = latest.get(self.entity_description.consumption_type)
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            return None

        item = items[0]
        values = item.get("values")
        if not isinstance(values, Mapping) or not values:
            return None

        date = sorted(str(key) for key in values)[-1]
        value = values.get(date)
        if not isinstance(value, (float, int)):
            return None

        return {
            "date": date,
            "value": value,
            "unit": item.get("unit"),
            "values_count": len(values),
            "primary": item.get("primary"),
        }

    def _series_point(self) -> dict[str, Any] | None:
        series_data = self.coordinator.data.get("series", {})
        if not isinstance(series_data, dict):
            return None

        series = series_data.get(self.entity_description.source)
        if not isinstance(series, dict):
            return None

        values = series.get("values")
        if not isinstance(values, list) or not values:
            return None

        points = [point for point in values if isinstance(point, dict) and isinstance(point.get("value"), (float, int))]
        if not points:
            return None

        point = max(points, key=lambda item: str(item.get("date", "")))
        return {
            "date": point.get("date"),
            "value": point.get("value"),
            "valueType": point.get("valueType"),
            "unit": series.get("unit"),
            "values_count": len(values),
            "dataSeriesType": series.get("dataSeriesType"),
        }


def _normalize_unit(unit: str) -> str:
    """Return a Home Assistant friendly unit."""
    if unit == "M_3":
        return UnitOfVolume.CUBIC_METERS
    if unit == "DEVICE_UNIT":
        return "device unit"
    return unit
