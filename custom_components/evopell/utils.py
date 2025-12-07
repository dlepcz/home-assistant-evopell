"""Utility functions for Evopell integration."""

import logging

from homeassistant.components.number import NumberDeviceClass, NumberMode
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTemperature

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

    for enum_cls, prefix in (
        (UnitOfTemperature, "UnitOfTemperature."),
        (UnitOfPower, "UnitOfPower."),
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
