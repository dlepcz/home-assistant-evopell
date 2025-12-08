"""async_setup_entry dla select Evopell."""

import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
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
    """Tworzy coordinator, pobiera pierwsze dane i rejestruje encje select."""
    name = config_entry.data[CONF_NAME]
    evopell = hass.data[DOMAIN][name]["evopell"]

    entities = []
    for tid, cfg in EVOPELL_PARAM_MAP1.items():
        if cfg.get("type") != "script":
            continue

        name = str(cfg.get("description", tid))
        options_dict = cfg.get("options")
        if not isinstance(options_dict, dict):
            continue
        options = list(options_dict.keys())

        entities.append(
            EvopellSelect(
                evopell,
                SelectEntityDescription(
                    key=tid,
                    name=name,
                    options=options,
                ),
                registers=options_dict,
            )
        )
    async_add_entities(entities)


class EvopellSelect(EvopellEntity, SelectEntity):
    """Representuje sensor Evopell."""

    def __init__(
        self,
        coordinator: EvopellCoordinator,
        description: SelectEntityDescription,
        registers: dict[str, dict[str, str]] | None,
    ) -> None:
        """Inicjalizuje encję sensora Evopell."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{self.coordinator.name}_{description.key}"
        self._registers = registers

    @property
    def current_option(self) -> str:
        """Get current option."""
        return ""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        _LOGGER.debug("Setting option to %s", option)
        if self._registers and option in self._registers:
            for k, v in self._registers[option].items():
                _LOGGER.debug("Would write %s to register %s", v, k)
            # registers = await self.coordinator.hub.async_write_register_values(
            # 0, self._registers[option]
            # )
            # if not registers:
            # _LOGGER.error(
            #    "Failed to write value %s to %s", value, self.entity_description.key
            # )
            # return
            # _LOGGER.debug("Written registers: %s", registers)

        self.async_write_ha_state()
