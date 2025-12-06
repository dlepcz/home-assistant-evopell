"""async_setup_entry dla sensorów Evopell."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, PERCENTAGE, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EvopellCoordinator, EvopellEntity
from .const import DOMAIN, EVOPELL_PARAM_MAP1

_LOGGER = logging.getLogger(__name__)


def parse_sensor_device_class(text: str | None) -> SensorDeviceClass | None:
    """Parses sensor device class from string."""
    if not text:
        return None
    prefix = "SensorDeviceClass."
    name = text.removeprefix(prefix)
    return getattr(SensorDeviceClass, name, None)


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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Tworzy coordinator, pobiera pierwsze dane i rejestruje encje sensorów."""
    name = config_entry.data[CONF_NAME]
    evopell = hass.data[DOMAIN][name]["evopell"]

    entities = []
    for tid, cfg in EVOPELL_PARAM_MAP1.items():
        if cfg.get("type") != "sensor":
            continue

        name = str(cfg.get("description", tid))

        evopell.hub.param_map[tid] = name  # Register parameter in hub's param_map
        device_class = parse_sensor_device_class(cfg.get("device_class"))  # type: ignore[arg-type]
        unit = parse_sensor_unit(cfg.get("native_unit_of_measurement"))  # type: ignore[arg-type]
        state_class = parse_sensor_state_class(cfg.get("state_class"))  # type: ignore[arg-type]
        icon = cfg.get("icon")  # type: ignore[arg-type]

        entities.append(
            EvopellSensor(
                evopell,
                SensorEntityDescription(
                    key=tid,
                    name=name,
                    device_class=device_class,
                    native_unit_of_measurement=unit,
                    state_class=state_class,
                    icon=icon,
                ),
            )
        )

    async_add_entities(entities)


class EvopellSensor(EvopellEntity, SensorEntity):
    """Representuje sensor Evopell."""

    def __init__(
        self, coordinator: EvopellCoordinator, description: SensorEntityDescription
    ) -> None:
        """Inicjalizuje encję sensora Evopell."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{self.coordinator.name}_{description.key}"

    @property
    def native_value(self) -> str | None:
        """Zwraca wartość sensora."""
        _LOGGER.debug("Native value for senosr %s", self.entity_description.key)
        return self.coordinator.data.get(self.entity_description.key)

    @callback
    def _handle_coordinator_update(self) -> None:
        _LOGGER.debug("Update senosr %s", self.entity_description.key)
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update extra attributes."""
