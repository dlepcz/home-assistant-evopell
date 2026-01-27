"""async_setup_entry dla sensorów Evopell."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from . import EvopellCoordinator, EvopellEntity
from .const import DOMAIN, EVOPELL_PARAM_MAP1, EVOPELL_PARMAS_TO_TEXT_MAP
from .store import AvgStore
from .utils import (
    epoch_to_datetime,
    find_sensor_entity_id,
    parse_float,
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

        avg = cfg.get("avg")  # type: ignore[arg-type]
        if avg:
            avg_str = str(avg)
        else:
            avg_str = None
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
        if avg_str is not None:
            _LOGGER.debug("Creating EvopellAverageSensor for %s", tid)
            avg = EvopellAverageSensor(
                hass,
                evopell,
                config_entry,
                name=avg_str,
                source_key=tid,
            )
            evopell.avg[tid] = avg
            entities.append(avg)

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
        result = None
        if tid in self.coordinator.hub.registers_data:
            register = self.coordinator.hub.registers_data[tid]
            if register is not None:
                result = register.value
        if result is None and isinstance(self.coordinator.data, dict):
            result = self.coordinator.data.get(tid)

        if result is not None and self.entity_description.device_class == "timestamp":
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


class EvopellAverageSensor(EvopellEntity, SensorEntity):
    """Running average (samples) of flue temperature."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: EvopellCoordinator,
        config_entry: ConfigEntry,
        name: str,
        source_key: str,
    ) -> None:
        """Initialize the average sensor."""
        super().__init__(coordinator)
        self.hass = hass
        self.config_entry = config_entry
        self.source_key = source_key
        self._attr_unique_id = f"{self.coordinator.name}_avg_{source_key}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None
        self._attr_state_class = None
        self._attr_icon = None
        self._attr_suggested_display_precision = None
        self._source_entity_id: str | None = None
        self._status_entity_id: str | None = None
        self.setAttrs()

        _LOGGER.debug(
            "EvopellAverageSensor key=%s source=%s status=%s",
            self._attr_unique_id,
            self._source_entity_id,
            self._status_entity_id,
        )

        # separate per config entry
        self._store = AvgStore(hass, key=self._attr_unique_id)

        self._unsub = None
        self._dirty_samples = 0

    @property
    def native_value(self) -> float | None:
        """Return the average value."""
        mean = self._store.state.mean
        return round(mean, 2) if mean is not None else None

    @callback
    def _handle_coordinator_update(self) -> None:
        _LOGGER.debug("Update senosr %s", self._attr_unique_id)
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update extra attributes."""
        st = self._store.state
        self._attr_extra_state_attributes = {
            "total": round(st.total, self._attr_suggested_display_precision or 2)
            if st.total is not None
            else None,
            "count": st.count,
        }
        _LOGGER.debug(
            "EvopellAverageSensor attrs updated: total=%s count=%s mean=%s",
            st.total,
            st.count,
            self.native_value,
        )

    async def async_added_to_hass(self) -> None:
        """Setup when entity is added."""
        await asyncio.sleep(0)
        await super().async_added_to_hass()
        await self._store.async_load()
        self.async_write_ha_state()
        self.setAttrs()
        if self._source_entity_id is None:
            _LOGGER.warning(
                "EvopellAverageSensor source entity not found, cannot track state changes"
            )
            return

        status = self.hass.states.get(self._source_entity_id)
        if status is None or status.state != "2":
            _LOGGER.debug("Evopell wrong status: %s", status)
            return

        # Optionally “seed” one sample at startup if source exists
        src = self.hass.states.get(self._source_entity_id)
        v0 = parse_float(src.state if src else None)
        if v0 is not None:
            st = self._store.state
            st.total += v0
            st.count += 1
            self._store.async_delay_save(30.0)
            self.async_write_ha_state()
            self._async_update_attrs()

        @callback
        def _on_change(event) -> None:
            _LOGGER.debug("EvopellAverageSensor _on_change event: %s", event)
            if self._status_entity_id is None:
                return
            status = self.hass.states.get(self._status_entity_id)
            if status is None or status.state != "2":
                _LOGGER.debug("Evopell wrong status: %s", status)
                return
            new_state = event.data.get("new_state")
            if new_state is None:
                return

            v = parse_float(new_state.state)
            if v is None:
                return

            st = self._store.state
            st.total += v
            st.count += 1

            self._dirty_samples += 1
            self.async_write_ha_state()

            # persist periodically (disk-friendly)
            if self._dirty_samples >= 10:
                self._dirty_samples = 0
                self._store.async_delay_save(30.0)

        self._unsub = async_track_state_change_event(
            self.hass, [self._source_entity_id], _on_change
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup when entity is removed."""
        if self._unsub:
            self._unsub()
            self._unsub = None
        await self._store.async_save()

    async def async_reset_average(self) -> None:
        """Reset the running average."""
        self._dirty_samples = 0
        await self._store.async_reset()
        self.async_write_ha_state()
        self._async_update_attrs()

    def setAttrs(self) -> None:
        """Set attributes dynamically."""
        if self._source_entity_id is None:
            self._source_entity_id = find_sensor_entity_id(
                self.hass,
                entry_id=self.config_entry.entry_id,
                unique_id=f"{self.coordinator.name}_{self.source_key}",
            )
        if self._source_entity_id is not None:
            if self._attr_unit_of_measurement is None:
                src = self.hass.states.get(self._source_entity_id)
                self._attr_native_unit_of_measurement = (
                    src.attributes.get("unit_of_measurement") if src else None
                )
                self._attr_device_class = (
                    src.attributes.get("device_class") if src else None
                )
                self._attr_state_class = (
                    src.attributes.get("state_class") if src else None
                )
                self._attr_icon = src.attributes.get("icon") if src else None
                self._attr_suggested_display_precision = (
                    src.attributes.get("suggested_display_precision") if src else 2
                )
        if self._status_entity_id is None:
            self._status_entity_id = find_sensor_entity_id(
                self.hass,
                entry_id=self.config_entry.entry_id,
                unique_id=f"{self.coordinator.name}_pl_status",
            )
        _LOGGER.debug(
            "EvopellAverageSensor source entity found: %s, units: %s, device_class: %s, state_class: %s, icon: %s, precision: %s",
            self._source_entity_id,
            self._attr_native_unit_of_measurement,
            self._attr_device_class,
            self._attr_state_class,
            self._attr_icon,
            self._attr_suggested_display_precision,
        )
