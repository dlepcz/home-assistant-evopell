
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
    DEFAULT_SCAN_INTERVAL,
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
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._name = name
        self._host = host
        self._port = port
        self._scan_interval = scan_interval
        self.evopell_data = {}

    def _update(self) -> dict:
        """Update."""
        try:
            return self.evopell_data
        except Exception as error:
            raise UpdateFailed(error) from error
    
    async def _async_update_data(self) -> dict:
        """Time to update."""
        try:
            return await self.hass.async_add_executor_job(self._update)
        except Exception as exc:
            raise UpdateFailed(f"Error updating evpell data: {exc}") from exc
