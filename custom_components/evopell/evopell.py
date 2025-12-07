"""Main classes for Evopell integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import timedelta
from itertools import islice
import logging
from typing import Any
from urllib.parse import urlencode

from aiohttp import BasicAuth, ClientError, ClientResponseError, ClientTimeout
from defusedxml import ElementTree as ET

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EvopellRegister:
    """Represents a single register entry returned by the device."""

    tid: str
    value: int | float | str
    description: str | None = None
    min_value: int | float | str | None = None
    max_value: int | float | str | None = None

    @staticmethod
    def from_xml_attrib(
        attrib: dict[str, str], description: str | None
    ) -> EvopellRegister | None:
        """Create register from XML attributes; returns None if required attrs are missing."""
        tid = attrib.get("tid")
        v = attrib.get("v")
        if not tid or v is None:
            return None

        return EvopellRegister(
            tid=tid,
            value=v,
            description=description,
            min_value=attrib.get("min"),
            max_value=attrib.get("max"),
        )


@dataclass(frozen=True, slots=True)
class EvopellWriteRegister:
    """Represents a single register entry returned by the device after write."""

    vid: str
    tid: str
    status: str

    @staticmethod
    def from_xml_attrib(
        attrib: dict[str, str], description: str | None
    ) -> EvopellWriteRegister | None:
        """Create register from XML attributes; returns None if required attrs are missing."""
        vid = attrib.get("vid")
        tid = attrib.get("tid")
        status = attrib.get("status")
        if not tid or not vid or not status:
            return None

        return EvopellWriteRegister(tid=tid, vid=vid, status=status)


class EvopellHub:
    """Async HTTP client for fetching register data from a device."""

    MAX_PARAMS_PER_REQUEST = 20

    def __init__(
        self,
        hass: HomeAssistant,
        base_url: str,
        username: str | None,
        password: str | None,
        timeout_seconds: int = 5,
        max_retries: int = 3,
        retry_delay: float = 1.5,
        param_map: dict[str, str] | None = None,
    ) -> None:
        """Initialize EvopellHub."""
        self._hass = hass
        self._session = async_get_clientsession(hass)
        self._timeout = ClientTimeout(total=timeout_seconds)

        self.base_url = base_url.rstrip("/")
        self.auth = (username, password) if username and password else None

        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self.param_map = {}
        self.device_info: DeviceInfo | None = None
        self.registers_data: dict[str, EvopellRegister] = {}

    async def async_read_device_info(self) -> bool:
        """Read device info and populate self.device_info."""
        registers = await self.async_fetch_registers(
            0,
            "device_id",
            "device_name",
            "device_soft_version",
            "device_type",
            "eth_mac",
            "device_hard_version",
            "eth_ip",
        )
        if len(registers) < 7:
            return False

        # Uwaga: trzymamy się Twojej kolejności
        device_id = str(registers[0].value)
        device_name = str(registers[1].value)
        sw_version = str(registers[2].value)
        model = str(registers[3].value)
        mac_raw = str(registers[4].value)
        hw_version = str(registers[5].value)
        ip = str(registers[6].value)

        mac_formatted = ":".join(mac_raw[i : i + 2] for i in range(0, 12, 2)).upper()
        configuration_url = f"http://{ip}"
        serial_number = f"{device_id}-{mac_raw}"

        self.device_info = DeviceInfo(
            identifiers={("evopell", serial_number)},
            name=device_name,
            manufacturer="Defro",
            model=model,
            sw_version=sw_version,
            hw_version=hw_version,
            connections={("MAC", mac_formatted)},
            configuration_url=configuration_url,
            serial_number=serial_number,
        )
        return True

    async def async_write_register_values(
        self, device_id: int, *params: dict[str, str]
    ) -> list[EvopellWriteRegister]:
        """Write register values to device."""
        return await self.async_write_registers(device_id, *params)

    async def async_write_registers(
        self, device_id: int, *params: dict[str, str]
    ) -> list[EvopellWriteRegister]:
        """Write registers to device."""
        all_registers: list[EvopellWriteRegister] = []
        if not params:
            _LOGGER.debug("No params passed — nothing to write")
            return all_registers

        for chunk in self._chunked(params, self.MAX_PARAMS_PER_REQUEST):
            registers = await self._async_write_chunk(device_id, chunk)
            all_registers.extend(registers)

        return all_registers

    async def async_fetch_register_values(
        self, device_id: int, *params: str
    ) -> dict[str, str]:
        """Fetch register values as a dictionary."""
        registers = await self.async_fetch_registers(device_id, *params)
        return {reg.tid: str(reg.value) for reg in registers}

    async def async_fetch_registers(
        self, device_id: int, *params: str
    ) -> list[EvopellRegister]:
        """Fetch registers from device.

        If no parameters are given, all keys from the param_map are used.
        Splits into multiple HTTP requests if necessary (max 20 params/request).
        """
        all_registers: list[EvopellRegister] = []
        if not params:
            if self.param_map:
                params = tuple(self.param_map.keys())
                _LOGGER.debug(
                    "No params passed — using all %d parameters from map", len(params)
                )
            else:
                _LOGGER.debug(
                    "No params passed and param_map is empty — nothing to fetch"
                )
                return all_registers

        _LOGGER.debug("Fetching registers %s from device %d", params, device_id)

        for chunk in self._chunked(params, self.MAX_PARAMS_PER_REQUEST):
            registers = await self._async_fetch_chunk(device_id, chunk)
            all_registers.extend(registers)

        for reg in all_registers:
            existing = self.registers_data.get(reg.tid)
            self.registers_data[reg.tid] = (
                reg
                if existing is None
                else replace(
                    existing,
                    value=reg.value,
                    description=reg.description,
                    min_value=reg.min_value,
                    max_value=reg.max_value,
                )
            )

        return all_registers

    async def _async_write_chunk(
        self, device_id: int, params_chunk: list[dict[str, str]]
    ) -> list[EvopellWriteRegister]:
        """Write one batch of registers."""
        merged: dict[str, str] = {}
        for d in params_chunk:
            merged.update(d)  # jeśli duplikaty kluczy, ostatni wygrywa

        query = urlencode(merged)
        url = f"{self.base_url}/setregister.cgi?device={device_id}&{query}"
        _LOGGER.debug("Writing to URL: %s", url)

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                async with self._session.get(
                    url,
                    timeout=self._timeout,
                    auth=self._build_auth(),
                ) as resp:
                    if resp.status in (401, 403):
                        _LOGGER.error(
                            "Authorization failed (401/403), stopping retries"
                        )
                        resp.raise_for_status()

                    resp.raise_for_status()
                    text = await resp.text()
                    return self._parse_xml_write_response(text)

            except ClientResponseError as err:
                last_error = err
                if err.status in (401, 403):
                    raise
                _LOGGER.warning(
                    "[Attempt %d/%d] HTTP error: %s",
                    attempt,
                    self.max_retries,
                    err,
                )

            except (ClientError, TimeoutError) as err:
                last_error = err
                _LOGGER.warning(
                    "[Attempt %d/%d] Network error: %s",
                    attempt,
                    self.max_retries,
                    err,
                )

            if attempt < self.max_retries:
                # Nie blokujemy event loop jak time.sleep
                await self._hass.async_add_executor_job(lambda: None)
                await self._hass.async_add_executor_job(lambda: None)
                await asyncio_sleep(self.retry_delay)

        _LOGGER.error("Max retry attempts reached, failing")
        if last_error:
            raise last_error
        return []

    async def _async_fetch_chunk(
        self, device_id: int, params_chunk: list[str]
    ) -> list[EvopellRegister]:
        """Fetch one batch of up to MAX_PARAMS_PER_REQUEST parameters."""
        query = "&".join(params_chunk)
        url = f"{self.base_url}/getregister.cgi?device={device_id}&{query}"
        _LOGGER.debug("Fetching from URL: %s", url)
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                async with self._session.get(
                    url,
                    timeout=self._timeout,
                    auth=self._build_auth(),
                ) as resp:
                    if resp.status in (401, 403):
                        _LOGGER.error(
                            "Authorization failed (401/403), stopping retries"
                        )
                        resp.raise_for_status()

                    resp.raise_for_status()
                    text = await resp.text()
                    return self._parse_xml_response(text)

            except ClientResponseError as err:
                last_error = err
                if err.status in (401, 403):
                    raise
                _LOGGER.warning(
                    "[Attempt %d/%d] HTTP error: %s",
                    attempt,
                    self.max_retries,
                    err,
                )

            except (ClientError, TimeoutError) as err:
                last_error = err
                _LOGGER.warning(
                    "[Attempt %d/%d] Network error: %s",
                    attempt,
                    self.max_retries,
                    err,
                )

            if attempt < self.max_retries:
                # Nie blokujemy event loop jak time.sleep
                await self._hass.async_add_executor_job(lambda: None)
                await self._hass.async_add_executor_job(lambda: None)
                await asyncio_sleep(self.retry_delay)

        _LOGGER.error("Max retry attempts reached, failing")
        if last_error:
            raise last_error
        return []

    def _build_auth(self):
        """Build aiohttp BasicAuth or return None."""
        if not self.auth:
            return None

        return BasicAuth(*self.auth)

    def _parse_xml_response(self, xml_text: str) -> list[EvopellRegister]:
        """Parse XML response into a list of register objects."""
        registers: list[EvopellRegister] = []
        root = ET.fromstring(xml_text)

        for reg in root.findall(".//reg"):
            item = EvopellRegister.from_xml_attrib(
                reg.attrib, self.param_map.get(reg.attrib.get("tid", ""))
            )
            if item is not None:
                registers.append(item)

        return registers

    def _parse_xml_write_response(self, xml_text: str) -> list[EvopellWriteRegister]:
        """Parse XML response into a list of register objects."""
        registers: list[EvopellWriteRegister] = []
        root = ET.fromstring(xml_text)

        for reg in root.findall(".//reg"):
            item = EvopellWriteRegister.from_xml_attrib(
                reg.attrib, self.param_map.get(reg.attrib.get("tid", ""))
            )
            if item is not None:
                registers.append(item)

        return registers

    @staticmethod
    def _chunked(iterable: Any, size: int):
        """Yield successive chunks (batches) of given size."""
        it = iter(iterable)
        while True:
            chunk = list(islice(it, size))
            if not chunk:
                break
            yield chunk

    async def async_close(self) -> None:
        """Close any resources if needed."""
        # HA zarządza sesją aiohttp, więc tu zwykle nic nie robimy
        return


# Minimalny, bezpieczny sleep async bez importu time.sleep
async def asyncio_sleep(seconds: float) -> None:
    """Async sleep helper."""

    await asyncio.sleep(seconds)


class EvopellCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Evopell data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        hub: EvopellHub,
        name: str,
        scan_interval: int,
    ) -> None:
        """Initialize EvopellCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=name,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.hub = hub

    async def _async_setup(self) -> None:
        """Run one-time setup before the first refresh."""
        ok = await self.hub.async_read_device_info()
        if not ok:
            raise UpdateFailed("Unable to read device info")

    async def _async_update_data(self) -> dict[str, str]:
        """Fetch fresh data for entities."""
        _LOGGER.debug("Fetching new data from Evopell device")
        try:
            return await self.hub.async_fetch_register_values(0)
        except Exception as err:
            raise UpdateFailed("Error updating evopell data") from err

    @property
    def device_info(self) -> DeviceInfo | None:
        """Expose device info collected by the hub."""
        return self.hub.device_info
