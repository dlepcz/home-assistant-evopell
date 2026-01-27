"""Button entity to reset the flue temperature average."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EvopellCoordinator, EvopellEntity
from .const import DOMAIN, EVOPELL_PARAM_MAP1

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the average reset button entity."""
    name = config_entry.data[CONF_NAME]
    evopell = hass.data[DOMAIN][name]["evopell"]

    entities = []
    for tid, cfg in EVOPELL_PARAM_MAP1.items():
        if cfg.get("type") != "sensor":
            continue
        if cfg.get("avg") is None:
            continue

        name = str(cfg.get("description", tid)).lower()
        name = f"Reset {name}"
        entities.append(EvopellAvgResetButton(evopell, tid, name))

    async_add_entities(entities)


class EvopellAvgResetButton(EvopellEntity, ButtonEntity):
    """Button to reset the flue temperature average."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EvopellCoordinator, key: str, name: str) -> None:
        """Initialize the reset button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.coordinator.name}_reset_avg_{key}"
        self._source_id = key
        self._attr_name = name
        _LOGGER.debug(
            "Created reset button for %s with unique_id %s and name %s",
            self._source_id,
            self._attr_unique_id,
            self._attr_name,
        )

    async def async_press(self) -> None:
        """Handle the button press to reset the average."""
        avg = self.coordinator.avg.get(self._source_id)  # type: ignore[union-attr]
        if avg:
            _LOGGER.debug("Resetting %s average", self._source_id)
            await avg.async_reset_average()
