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

DEVICE_SERIES_META = {
    "heat_devices_month": {
        "label": "Ogrzewanie",
        "period": "miesiac",
        "unit": None,
        "device_class": None,
    },
    "heat_devices_day": {
        "label": "Ogrzewanie",
        "period": "dzien",
        "unit": None,
        "device_class": None,
    },
    "hot_water_devices_month": {
        "label": "Ciepla woda",
        "period": "miesiac",
        "unit": UnitOfVolume.CUBIC_METERS,
        "device_class": SensorDeviceClass.WATER,
    },
    "hot_water_devices_day": {
        "label": "Ciepla woda",
        "period": "dzien",
        "unit": UnitOfVolume.CUBIC_METERS,
        "device_class": SensorDeviceClass.WATER,
    },
    "cold_water_devices_month": {
        "label": "Zimna woda",
        "period": "miesiac",
        "unit": UnitOfVolume.CUBIC_METERS,
        "device_class": SensorDeviceClass.WATER,
    },
    "cold_water_devices_day": {
        "label": "Zimna woda",
        "period": "dzien",
        "unit": UnitOfVolume.CUBIC_METERS,
        "device_class": SensorDeviceClass.WATER,
    },
}


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
    entities: list[SensorEntity] = [
        IstaConsumptionSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    ]
    entities.extend(_device_sensors(coordinator))

    async_add_entities(entities)


def _device_sensors(coordinator: PyConnectIstaDataUpdateCoordinator) -> list[SensorEntity]:
    """Create per-meter sensors from the API metering points."""
    device_series = coordinator.data.get("device_series", {})
    if not isinstance(device_series, dict):
        return []

    entities: list[SensorEntity] = []
    for source, meta in DEVICE_SERIES_META.items():
        series = device_series.get(source)
        if not isinstance(series, dict):
            continue

        metering_points = series.get("meteringPoints")
        if not isinstance(metering_points, list):
            continue

        for metering_point in metering_points:
            if not isinstance(metering_point, dict):
                continue
            index = metering_point.get("index")
            serial_number = metering_point.get("serialNumber")
            if not isinstance(index, int) or not serial_number:
                continue

            entities.append(
                IstaDeviceConsumptionSensor(
                    coordinator=coordinator,
                    source=source,
                    index=index,
                    serial_number=str(serial_number),
                    device_type=str(metering_point.get("deviceType", "")),
                    label=str(meta["label"]),
                    period=str(meta["period"]),
                    unit=meta["unit"],
                    device_class=meta["device_class"],
                )
            )

    return entities


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


class IstaDeviceConsumptionSensor(CoordinatorEntity[PyConnectIstaDataUpdateCoordinator], SensorEntity):
    """Per-device consumption sensor for ista Connect."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = False
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coordinator: PyConnectIstaDataUpdateCoordinator,
        source: str,
        index: int,
        serial_number: str,
        device_type: str,
        label: str,
        period: str,
        unit: str | None,
        device_class: SensorDeviceClass | None,
    ) -> None:
        """Initialize the per-device sensor."""
        super().__init__(coordinator)
        self._source = source
        self._index = index
        self._serial_number = serial_number
        self._device_type = device_type
        self._attr_name = f"{label} {serial_number} - {period}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{source}_{serial_number}_{index}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_{serial_number}")},
            manufacturer=MANUFACTURER,
            name=f"{NAME} {serial_number}",
            model=device_type or "istaConnect metering point",
            via_device=(DOMAIN, coordinator.config_entry.entry_id),
        )

    @property
    def native_value(self) -> float | int | None:
        """Return the latest value for this meter."""
        point = self._point
        value = point.get("value") if point else None
        return value if isinstance(value, (float, int)) else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return native unit from API when available."""
        point = self._point
        unit = point.get("unit") if point else None
        if isinstance(unit, str):
            return _normalize_unit(unit)
        return self._attr_native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return meter metadata."""
        point = self._point
        attrs: dict[str, Any] = {
            "serial_number": self._serial_number,
            "device_type": self._device_type,
            "meter_index": self._index,
            "source": self._source,
        }
        if not point:
            return attrs

        attrs.update(
            {
                "date": point.get("date"),
                "ratio": point.get("ratio"),
                "unit": point.get("unit"),
                "values_count": point.get("values_count"),
                "data_series_type": point.get("dataSeriesType"),
            }
        )
        return attrs

    @property
    def _point(self) -> dict[str, Any] | None:
        device_series = self.coordinator.data.get("device_series", {})
        if not isinstance(device_series, dict):
            return None

        series = device_series.get(self._source)
        if not isinstance(series, dict):
            return None

        values = series.get("values")
        if not isinstance(values, Mapping) or not values:
            return None

        for date in sorted((str(key) for key in values), reverse=True):
            day_values = values.get(date)
            if not isinstance(day_values, list):
                continue
            for item in day_values:
                if not isinstance(item, dict):
                    continue
                if item.get("index") == self._index and isinstance(item.get("value"), (float, int)):
                    return {
                        "date": date,
                        "value": item.get("value"),
                        "ratio": item.get("ratio"),
                        "unit": series.get("unit"),
                        "values_count": len(values),
                        "dataSeriesType": series.get("dataSeriesType"),
                    }

        return None
