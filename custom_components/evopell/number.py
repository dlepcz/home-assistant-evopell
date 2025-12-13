"""Number platform for Evopell integration."""

from dataclasses import replace
import logging

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EvopellCoordinator, EvopellEntity
from .const import DOMAIN, EVOPELL_PARAM_MAP1
from .utils import (
    parse_number_device_class,
    parse_number_mode,
    parse_sensor_unit,
    to_float,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Tworzy coordinator, pobiera pierwsze dane i rejestruje encje sensorów."""
    _LOGGER.debug("Setup number for %s", config_entry.data[CONF_NAME])
    name = config_entry.data[CONF_NAME]
    evopell = hass.data[DOMAIN][name]["evopell"]

    entities = []
    for tid, cfg in EVOPELL_PARAM_MAP1.items():
        if cfg.get("type") != "number":
            continue

        name = str(cfg.get("description", tid))

        evopell.hub.param_map[tid] = name  # Register parameter in hub's param_map
        device_class = parse_number_device_class(cfg.get("device_class"))  # type: ignore[arg-type]
        unit = parse_sensor_unit(cfg.get("native_unit_of_measurement"))  # type: ignore[arg-type]
        icon = str(cfg.get("icon"))  # type: ignore[arg-type]
        mode = parse_number_mode(cfg.get("mode"))  # type: ignore[arg-type]
        step = to_float(str(cfg.get("step")))
        entities.append(
            EvopellNumber(
                evopell,
                NumberEntityDescription(
                    key=tid,
                    name=name,
                    device_class=device_class,
                    native_unit_of_measurement=unit,
                    icon=icon,
                    mode=mode,
                    native_step=step,
                ),
            )
        )

    async_add_entities(entities)


class EvopellNumber(EvopellEntity, NumberEntity):
    """Representuje sensor Evopell."""

    def __init__(
        self,
        coordinator: EvopellCoordinator,
        description: NumberEntityDescription,
    ) -> None:
        """Inicjalizuje encję sensora Evopell."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{self.coordinator.name}_{description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        register = self.coordinator.hub.registers_data.get(self.entity_description.key)
        if register:
            if register.min_value is not None:
                min_val = to_float(str(register.min_value))
                if min_val is not None:
                    self._attr_native_min_value = min_val
            if register.max_value is not None:
                max_val = to_float(str(register.max_value))
                if max_val is not None:
                    self._attr_native_max_value = max_val

        super()._handle_coordinator_update()

    @property
    def native_value(self) -> float | None:
        """Get native value."""
        tid = self.entity_description.key
        _LOGGER.debug("Native value for number %s", tid)
        result = None
        if tid in self.coordinator.hub.registers_data:
            register = self.coordinator.hub.registers_data[tid]
            if register is not None:
                result = register.value

        if result is None and isinstance(self.coordinator.data, dict):
            result = self.coordinator.data.get(tid)

        if result is not None:
            value = to_float(str(result))
            return value if value is not None else 0.0

        return None

    async def async_set_native_value(self, value: float) -> None:
        """Change the selected value."""
        _LOGGER.debug("Write value %s to %s", value, self.entity_description.key)
        registers = await self.coordinator.hub.async_write_register_values(
            0, {self.entity_description.key: str(value)}
        )

        if not registers:
            _LOGGER.error(
                "Failed to write value %s to %s", value, self.entity_description.key
            )
            return
        _LOGGER.debug("Written registers: %s", registers)
        for k in registers:
            if k.status == "ok":
                self.coordinator.data[k.tid] = k.value
                if k.tid in self.coordinator.hub.registers_data:
                    reg = self.coordinator.hub.registers_data[k.tid]
                    self.coordinator.hub.registers_data[k.tid] = replace(
                        reg,
                        value=k.value,
                        description=reg.description,
                        min_value=reg.min_value,
                        max_value=reg.max_value,
                    )
            else:
                _LOGGER.error("Failed to write register %s: status %s", k.tid, k.status)
        self.async_write_ha_state()
