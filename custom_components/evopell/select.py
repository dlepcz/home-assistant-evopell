"""async_setup_entry dla select Evopell."""

from dataclasses import replace
import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EvopellCoordinator, EvopellEntity
from .const import DOMAIN, EVOPELL_PARAM_MAP1, EVOPELL_PARMAS_TO_TEXT_MAP

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
                readOnly=False,
                registers=options_dict,
            )
        )

    for k, v in EVOPELL_PARMAS_TO_TEXT_MAP.items():
        entities.append(
            EvopellSelect(
                evopell,
                SelectEntityDescription(
                    key=k,
                    name=str(EVOPELL_PARAM_MAP1[k].get("description", k)),
                    options=list(v.values()),
                ),
                readOnly=True,
                registers=None,
            )
        )

    async_add_entities(entities)


class EvopellSelect(EvopellEntity, SelectEntity):
    """Representuje sensor Evopell."""

    def __init__(
        self,
        coordinator: EvopellCoordinator,
        description: SelectEntityDescription,
        readOnly: bool,
        registers: dict[str, dict[str, str]] | None,
    ) -> None:
        """Inicjalizuje encję sensora Evopell."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{self.coordinator.name}_{description.key}"
        self._registers = registers
        self._readOnly = readOnly

    @property
    def current_option(self) -> str | None:
        """Get current option."""
        _LOGGER.debug("Current option for select %s", self.entity_description.key)
        if self.entity_description.key in self.coordinator.hub.registers_data:
            _LOGGER.debug("Found register for select %s", self.entity_description.key)
            value = self.coordinator.hub.registers_data[self.entity_description.key]
            if value is not None:
                _LOGGER.debug(
                    "Value for select %s: %s", self.entity_description.key, value
                )
                if self.entity_description.key in EVOPELL_PARMAS_TO_TEXT_MAP:
                    text_map = EVOPELL_PARMAS_TO_TEXT_MAP[self.entity_description.key]
                    _LOGGER.debug(
                        "Text map for select %s: %s -> %s",
                        self.entity_description.key,
                        text_map,
                        text_map.get(str(value.value), ""),
                    )
                    return text_map.get(str(value.value), "")
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if not self._readOnly:
            _LOGGER.debug("Setting option to %s", option)
            if self._registers and option in self._registers:
                for k, v in self._registers[option].items():
                    _LOGGER.debug("Would write %s to register %s", v, k)

                registers = await self.coordinator.hub.async_write_register_values(
                    0, self._registers[option]
                )
                if not registers:
                    _LOGGER.debug("No registers written")
                    return

                _LOGGER.debug("Written registers: %s", registers)
                for k in registers:
                    if k.status == "ok":
                        if k.tid in self.coordinator.hub.registers_data:
                            self.coordinator.data[k.tid] = k.value
                            _LOGGER.debug(
                                "Updated coordinator data: %s to %s", k.tid, k.value
                            )
                            reg = self.coordinator.hub.registers_data[k.tid]
                            self.coordinator.hub.registers_data[k.tid] = replace(
                                reg,
                                value=k.value,
                                description=reg.description,
                                min_value=reg.min_value,
                                max_value=reg.max_value,
                            )
                    else:
                        _LOGGER.error(
                            "Failed to write register %s: status %s", k.tid, k.status
                        )

        self.async_write_ha_state()
