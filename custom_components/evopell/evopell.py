
import logging
from datetime import timedelta
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.const import CONF_NAME
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.core import HomeAssistant

from .const import (
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

class Evopell(DataUpdateCoordinator):
     def __init__(
        self, 
        hass: HomeAssistant,
        name,
        host,
        port,
        scan_interval,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self._name = name
        self._host = host
        self._port = port
        self._scan_interval = scan_interval
        