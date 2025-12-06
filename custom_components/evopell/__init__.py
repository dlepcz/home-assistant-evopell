"""The Evopell http Integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_EVOPELL_PASSWORD, CONF_EVOPELL_USER, DOMAIN, EVOPELL_PARAM_MAP
from .evopell import EvopellCoordinator, EvopellHub

# PLATFORMS = ["number", "select", "sensor", "binary_sensor"]
PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config):
    """Inicjalizacja integracji na etapie YAML (zwykle pusta dla integracji z config_flow)."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Uruchamia instancję integracji na podstawie wpisu konfiguracji (dodanej w UI)."""

    host = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]
    port = entry.data[CONF_PORT]
    scan_interval = entry.data[CONF_SCAN_INTERVAL]

    _LOGGER.debug("Setup %s.%s", DOMAIN, name)

    hub = EvopellHub(
        hass,
        base_url=f"http://{host}:{port}",
        username=entry.data[CONF_EVOPELL_USER],
        password=entry.data[CONF_EVOPELL_PASSWORD],
        timeout_seconds=5,
        max_retries=3,
        param_map=EVOPELL_PARAM_MAP,
    )
    coordinator = EvopellCoordinator(hass, entry, hub, name, scan_interval)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][name] = {"evopell": coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry):
    """Zdejmuje integrację i jej platformy, gdy użytkownik ją usuwa/wyłącza."""
    evopell: EvopellCoordinator = hass.data[DOMAIN][entry.data["name"]]["evopell"]
    await evopell.hub.async_close()
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.data["name"])
    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry, device_entry
) -> bool:
    """Remove a config entry from a device."""
    return True


class EvopellEntity(CoordinatorEntity[EvopellCoordinator]):
    """Main class for Evopell entities."""

    def __init__(self, coordinator: EvopellCoordinator) -> None:
        """Inicjalizacja encji powiązanej z koordynatorem."""
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Device info."""
        return self.coordinator.device_info
