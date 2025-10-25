
import logging
import requests
import time
import xml.etree.ElementTree as ET
from itertools import islice
from datetime import timedelta
from typing import Optional, List, Dict
from homeassistant.config_entries import ConfigEntry
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

class EvopellRegister:
    """Represents a single register entry returned by the device."""

    def __init__(
        self,
        tid: str,
        v: str,
        description: Optional[str] = None,
        min_value: Optional[str] = None,
        max_value: Optional[str] = None,
    ):
        self.tid = tid
        self.v = self._convert_value(v)
        self.min = self._convert_value(min_value)
        self.max = self._convert_value(max_value)
        self.description = description

    def __repr__(self):
        desc = f" desc='{self.description}'" if self.description else ""
        return f"<Register tid={self.tid} v={self.v} min={self.min} max={self.max}{desc}>"

    @staticmethod
    def _convert_value(value: Optional[str]):
        """Try to convert string to int or float when possible."""
        if value is None:
            return None
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return value

class EvopellHub:
    """
    Synchronous HTTP client for fetching register data from a device.
    Supports HTTP BasicAuth, retries, timeouts, parameter batching, and parameter descriptions.
    """

    MAX_PARAMS_PER_REQUEST = 20

    def __init__(
        self,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout_seconds: int = 5,
        max_retries: int = 3,
        retry_delay: float = 1.5,
        param_map: Optional[Dict[str, str]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth = (username, password) if username and password else None
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.param_map = param_map or {}
        self.device_info = {}

    def fetch_registers(self, device_id: int, *params: str) -> List[EvopellRegister]:
        """
        Fetch registers from device.
        If no parameters are given, all keys from the param_map are used.
        Splits into multiple HTTP requests if necessary (max 20 params/request).
        """
        # 🔹 Użycie wszystkich parametrów z mapy, jeśli użytkownik nie poda żadnych
        if not params:
            if not self.param_map:
                raise ValueError("No parameters provided and parameter map is empty.")
            params = tuple(self.param_map.keys())
            _LOGGER.debug(f"No params passed — using all {len(params)} parameters from map.")

        all_registers: List[EvopellRegister] = []
        for chunk in self._chunked(params, self.MAX_PARAMS_PER_REQUEST):
            all_registers.extend(self._fetch_chunk(device_id, chunk))
        return all_registers

    async def read_device_info(self):
        #registers: List[EvopellRegister] = self.fetch_registers(0,"device_id","device_name","device_soft_version", "device_type", "eth_mac", "device_hard_version","eth_ip");
        #if not registers:
        #    return False
            
        #device_id = registers[0].v
        #sw_version = registers[2].v
        #model = registers[3].v
        #mac = registers[4].v
        #mac_formatted = ":".join(mac[i:i+2] for i in range(0, 12, 2)).upper()
        #hw_version = registers[5].v
        #ip = registers[6].v
        #url = f"http://{ip}"

        model = "test"
        sw_version = "sw"
        hw_version = "hw"
        device_id = 1
        mac_formatted = "q"
        url = "u"
        self.device_info = {
            "manufacturer": "Defro",
            "model": model,
            "sw_version": sw_version,
            "hw_version": hw_version,
            "device_id": device_id,
            "connections" : {("MAC", mac_formatted)},
            "configuration_url": url
        }

        return True
    
    def fetch_register_values(self, device_id: int, *params: str) -> Dict[str, str]:
        if not params:
            params = tuple(self.param_map.keys())
            _LOGGER.debug(f"No params passed — using all {len(params)} parameters from map.")

        registers = self.fetch_registers(device_id, *params)
        return {reg.tid: str(reg.v) for reg in registers}

    def _fetch_chunk(self, device_id: int, params_chunk: List[str]) -> List[EvopellRegister]:
        """Fetch one batch of up to MAX_PARAMS_PER_REQUEST parameters."""
        query = "&".join(params_chunk)
        url = f"{self.base_url}/getregister.cgi?device={device_id}&{query}"

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.get(url, auth=self.auth, timeout=self.timeout_seconds)
                if response.status_code in (401, 403):
                    _LOGGER.error("Authorization failed (401/403). Stopping retries.")
                    response.raise_for_status()

                response.raise_for_status()
                return self._parse_xml_response(response.text)

            except requests.HTTPError as e:
                if response.status_code in (401, 403):
                    raise
                _LOGGER.warning(f"[Attempt {attempt}/{self.max_retries}] HTTP error: {e}")

            except (requests.RequestException, requests.Timeout) as e:
                _LOGGER.warning(f"[Attempt {attempt}/{self.max_retries}] Network error: {e}")

            if attempt < self.max_retries:
                time.sleep(self.retry_delay)
            else:
                _LOGGER.error("Max retry attempts reached. Failing.")
                raise

    def _parse_xml_response(self, xml_text: str) -> List[EvopellRegister]:
        """Parse XML response into a list of Register objects."""
        registers = []
        root = ET.fromstring(xml_text)
        for reg in root.findall(".//reg"):
            tid = reg.attrib.get("tid")
            v = reg.attrib.get("v")
            min_value = reg.attrib.get("min")
            max_value = reg.attrib.get("max")
            description = self.param_map.get(tid)
            registers.append(EvopellRegister(tid, v, description, min_value, max_value))
        return registers

    @staticmethod
    def _chunked(iterable, size):
        """Yield successive chunks (batches) of given size."""
        it = iter(iterable)
        while True:
            chunk = list(islice(it, size))
            if not chunk:
                break
            yield chunk

class EvopellCoordinator(DataUpdateCoordinator):
    def __init__(
        self, 
        hass: HomeAssistant,
        entry: ConfigEntry,
        hub: EvopellHub,
        name,
        scan_interval,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=name,
            update_interval=timedelta(seconds=scan_interval),
        )
        self._name = name
        self._hub = hub
        self._scan_interval = scan_interval
        self.evopell_data = {}

    async def _async_setup(self):
        if not await self._hub.read_device_info():
            raise UpdateFailed("Unable to read device info")
        
    def _update(self) -> dict:
        """Update."""
        try:
            self.evopell_data = self._hub.fetch_register_values(0)
            return self.evopell_data
        except Exception as error:
            raise UpdateFailed(error) from error
    
    async def _async_update_data(self) -> dict:
        """Time to update."""
        try:
            return await self.hass.async_add_executor_job(self._update)
        except Exception as exc:
            raise UpdateFailed(f"Error updating evpell data: {exc}") from exc
    
    @property
    def device_info(self):
        return self._hub.device_info