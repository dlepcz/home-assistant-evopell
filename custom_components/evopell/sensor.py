"""async_setup_entry dla sensorów Evopell."""

import logging

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EvopellCoordinator, EvopellEntity
from .const import DOMAIN, EVOPELL_PARAM_MAP1
from .utils import (
    parse_sensor_device_class,
    parse_sensor_state_class,
    parse_sensor_unit,
)

_LOGGER = logging.getLogger(__name__)


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
        try:
            display_precision = int(str(cfg.get("display_precision")))
        except ValueError:
            display_precision = None

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
                    suggested_display_precision=display_precision,
                ),
            )
        )

        match tid:
            case "zaw4d_dir" | "tryb_auto_state" | "pl_status":
                entities.append(
                    EvopellSensor(
                        evopell,
                        SensorEntityDescription(
                            key=f"{tid}_text",
                            name=f"{name} (text)",
                            device_class=None,
                            native_unit_of_measurement=None,
                            state_class=None,
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
        tid = self.entity_description.key
        _LOGGER.debug("Native value for senosr %s", tid)
        result = self.coordinator.data.get(tid)
        if tid.endswith("_text"):
            prefix = tid.removesuffix("_text")
            result = self.coordinator.data.get(prefix)
            match prefix:
                case "tryb_auto_state":
                    match result:
                        case "0":
                            result = "Ręczny"
                        case "1":
                            result = "Automatyczny"
                        case "2":
                            result = "Alarmowy"
                        case _:
                            result = "Nieznany"
                case "zaw4d_dir":
                    if result == "1":
                        result = "Lewo"
                    else:
                        result = "Prawo"
                case "pl_status":
                    match result:
                        case "0":
                            result = "Stop"
                        case "1":
                            result = "Rozpalanie"
                        case "2":
                            result = "Praca"
                        case "3":
                            result = "Wygaszanie"
                        case "4":
                            result = "Czyszczenie"
                        case _:
                            result = "Nieznany"
        return result

    @callback
    def _handle_coordinator_update(self) -> None:
        _LOGGER.debug("Update senosr %s", self.entity_description.key)
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update extra attributes."""
        tid = self.entity_description.key
        if tid.endswith("_text"):
            tid = tid.removesuffix("_text")
        register = self.coordinator.hub.registers_data[tid]
        if register is not None:
            self._attr_extra_state_attributes = {
                "min": register.min_value,
                "max": register.max_value,
            }
