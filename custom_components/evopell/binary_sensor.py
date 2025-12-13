"""async_setup_entry dla sensorów Evopell."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EvopellCoordinator, EvopellEntity
from .const import DOMAIN, EVOPELL_PARAM_MAP1

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Tworzy coordinator, pobiera pierwsze dane i rejestruje encje sensorów."""
    _LOGGER.debug("Setup binary_sensor for %s", config_entry.data[CONF_NAME])
    name = config_entry.data[CONF_NAME]
    evopell = hass.data[DOMAIN][name]["evopell"]

    entities = []
    for tid, cfg in EVOPELL_PARAM_MAP1.items():
        if cfg.get("type") != "binary_sensor":
            continue

        name = str(cfg.get("description", tid))
        icon = str(cfg.get("icon"))
        evopell.hub.param_map[tid] = name
        entities.append(
            EvopellBinarySensor(
                evopell,
                BinarySensorEntityDescription(
                    key=tid,
                    name=name,
                    icon=icon,
                ),
            )
        )
    async_add_entities(entities)


class EvopellBinarySensor(EvopellEntity, BinarySensorEntity):
    """Representuje sensor Evopell."""

    def __init__(
        self,
        coordinator: EvopellCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Inicjalizuje encję sensora Evopell."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{self.coordinator.name}_{description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Przelicza stan na podstawie najnowszych danych z koordynatora."""
        self._attr_is_on = _to_bool(self._get_register_value())
        super()._handle_coordinator_update()

    def _get_register_value(self):
        reg = self.coordinator.hub.registers_data.get(self.entity_description.key)
        return None if reg is None else reg.value

    @property
    def is_on(self) -> bool | None:
        """Zwraca stan encji."""
        return self._attr_is_on


def _to_bool(value) -> bool | None:
    """Konwertuje typowe wartości z urządzeń na bool."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("1", "true", "on", "yes", "open", "alarm"):
            return True
        if v in ("0", "false", "off", "no", "closed", "ok"):
            return False
    return None
