import logging
from .evopell import EvopellCoordinator, EvopellHub
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    EVOPELL_PARAM_MAP,
    CONF_EVOPELL_USER,
    CONF_EVOPELL_PASSWORD,
)

#PLATFORMS = ["number", "select", "sensor", "binary_sensor"]
PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config):
    hass.data[DOMAIN] = {}
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    host = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]
    scan_interval = entry.data[CONF_SCAN_INTERVAL]

    _LOGGER.debug("Setup %s.%s", DOMAIN, name)

    hub = EvopellHub(
        base_url= f"http://{host}",
        username=entry.data[CONF_EVOPELL_USER],
        password=entry.data[CONF_EVOPELL_PASSWORD],
        timeout_seconds=5,
        max_retries=3,
        param_map=EVOPELL_PARAM_MAP,
    )
    coordinator = EvopellCoordinator(
        hass, 
        entry,
        hub,
        name, 
        scan_interval)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][name] = {"evopell": coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry):
    evopell: EvopellCoordinator = hass.data[DOMAIN][entry.data["name"]]["evopell"]
    await evopell.close()
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.data["name"])

async def async_remove_config_entry_device(
    hass: HomeAssistant, entry, device_entry
) -> bool:
    """Remove a config entry from a device."""
    return True


class EvopellEntity(CoordinatorEntity):

    def __init__(self, coordinator: EvopellCoordinator) -> None:
        """Init SolarEdgeEntity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
