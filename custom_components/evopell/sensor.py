"""async_setup_entry dla sensorów Evopell."""

import logging

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EvopellCoordinator, EvopellEntity
from .const import DOMAIN, EVOPELL_PARAM_MAP1, EVOPELL_PARMAS_TO_TEXT_MAP
from .utils import (
    epoch_to_datetime,
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
        if icon:
            icon_str = str(icon)
        else:
            icon_str = None
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
                    icon=icon_str,
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
                            icon=icon_str,
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
    def native_value(self):
        """Zwraca wartość sensora."""
        tid = self.entity_description.key
        _LOGGER.debug("Native value for senosr %s", tid)
        result = self.coordinator.data.get(tid)
        if tid.endswith("_text"):
            prefix = tid.removesuffix("_text")
            result = self.coordinator.data.get(prefix)
            text_map = EVOPELL_PARMAS_TO_TEXT_MAP.get(prefix)
            if text_map and result in text_map:
                result = text_map[result]
            else:
                result = "Nieznany"
        if self.entity_description.device_class == "timestamp" and result is not None:
            result = epoch_to_datetime(result)
        return result

    @callback
    def _handle_coordinator_update(self) -> None:
        _LOGGER.debug("Update senosr %s", self.entity_description.key)
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update extra attributes."""
        if self.entity_description.device_class != "timestamp":
            tid = self.entity_description.key
            if tid.endswith("_text"):
                tid = tid.removesuffix("_text")
            register = self.coordinator.hub.registers_data[tid]
            if register is not None:
                extra_attrs = {}
                if register.min_value:
                    extra_attrs["min"] = register.min_value
                if register.max_value:
                    extra_attrs["max"] = register.max_value
                if tid in EVOPELL_PARMAS_TO_TEXT_MAP:
                    extra_attrs.update(
                        {v: k for k, v in EVOPELL_PARMAS_TO_TEXT_MAP[tid].items()}
                    )

                self._attr_extra_state_attributes = extra_attrs
