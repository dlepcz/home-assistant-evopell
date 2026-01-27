"""Utility functions for Evopell integration."""

from datetime import UTC, datetime
import logging

from homeassistant.components.number import NumberDeviceClass, NumberMode
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)


def parse_sensor_device_class(text: str | None) -> SensorDeviceClass | None:
    """Parses sensor device class from string."""
    if not text:
        return None
    prefix = "SensorDeviceClass."
    name = text.removeprefix(prefix)
    return getattr(SensorDeviceClass, name, None)


def parse_number_device_class(text: str | None) -> NumberDeviceClass | None:
    """Parses number device class from string."""
    if not text:
        return None
    prefix = "SensorDeviceClass."
    name = text.removeprefix(prefix)
    return getattr(SensorDeviceClass, name, None)


def parse_number_mode(text: str | None) -> NumberMode | None:
    """Parses number mode from string."""
    if not text:
        return None
    prefix = "NumberMode."
    name = text.removeprefix(prefix)
    return getattr(NumberMode, name, None)


def parse_sensor_unit(text: str | None) -> str | None:
    """Parse HA unit string to its value (e.g. UnitOfTemperature.CELSIUS, UnitOfPower.KILO_WATT, PERCENTAGE)."""
    if not text:
        return None

    # Support constant percentage
    if text == "PERCENTAGE":
        return PERCENTAGE  # "%"

    if text.startswith("OWN."):
        return text.removeprefix("OWN.")

    for enum_cls, prefix in (
        (UnitOfTemperature, "UnitOfTemperature."),
        (UnitOfPower, "UnitOfPower."),
        (UnitOfVolumeFlowRate, "UnitOfMassFlowRate."),
        (UnitOfPressure, "UnitOfPressure."),
    ):
        if text.startswith(prefix):
            name = text.removeprefix(prefix)
            unit = getattr(enum_cls, name, None)
            return unit.value if unit else None

    return None


def parse_sensor_state_class(text: str | None) -> SensorStateClass | None:
    """Parses sensor state class from string."""
    if not text:
        return None
    prefix = "SensorStateClass."
    name = text.removeprefix(prefix)
    return getattr(SensorStateClass, name, None)


def to_float(value: str | None) -> float | None:
    """Convert string to float, handling commas and errors."""
    if value is None:
        return None
    try:
        return float(value.strip().replace(",", "."))
    except (ValueError, AttributeError):
        return None


def epoch_to_datetime(value: str | float | None) -> datetime | None:
    """Convert epoch timestamp to datetime object in UTC."""
    if value is None:
        return None
    try:
        ts = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(ts, tz=UTC)


def parse_float(value: str | None) -> float | None:
    """Parse string to float, returning None for invalid values."""
    if not value or value in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return None
    try:
        v = float(value)
    except (ValueError, TypeError):
        return None
    if v != v:  # NaN
        return None
    return v


def find_sensor_entity_id(
    hass: HomeAssistant,
    *,
    entry_id: str,
    unique_id: str,
) -> str | None:
    """Find sensor entity_id by unique_id within a config entry."""
    reg = er.async_get(hass)
    for e in er.async_entries_for_config_entry(reg, entry_id):
        if e.domain == "sensor" and e.unique_id == unique_id:
            return e.entity_id
    return None
