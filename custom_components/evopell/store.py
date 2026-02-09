"""Small persisted store for running average."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

_STORAGE_VERSION = 1
_LOGGER = logging.getLogger(__name__)


@dataclass
class AvgState:
    """Dataclass for storing average state."""

    total: float = 0.0
    count: int = 0
    min_value: float = 0.0
    max_value: float = 0.0

    @property
    def mean(self) -> float | None:
        """Calculate and return the mean value."""
        return self.total / self.count if self.count else None


class AvgStore:
    """Small persisted store for running average."""

    def __init__(self, hass: HomeAssistant, key: str) -> None:
        """Initialize the AvgStore."""
        self._store: Store[dict] = Store(hass, _STORAGE_VERSION, key)
        self.state = AvgState()

    async def async_load(self) -> None:
        """Load the stored state from storage."""
        data = await self._store.async_load()
        if not data:
            return
        self.state = AvgState(
            total=float(data.get("total", 0.0)),
            count=int(data.get("count", 0)),
            min_value=float(data.get("min_value", 0.0)),
            max_value=float(data.get("max_value", 0.0)),
        )
        _LOGGER.debug(
            "AvgStore loaded state for %s: total=%s count=%s mean=%s",
            self._store.key,
            self.state.total,
            self.state.count,
            self.state.mean,
        )

    async def async_save(self) -> None:
        """Save the current state to storage."""
        await self._store.async_save(asdict(self.state))
        _LOGGER.info(
            "AvgStore saved state for %s: total=%s count=%s mean=%s",
            self._store.key,
            self.state.total,
            self.state.count,
            self.state.mean,
        )

    def async_delay_save(self, delay: float = 30.0) -> None:
        """Schedule a delayed save of the current state."""
        _LOGGER.debug(
            "AvgStore saved state: total=%s count=%s mean=%s",
            self.state.total,
            self.state.count,
            self.state.mean,
        )
        self._store.async_delay_save(lambda: asdict(self.state), delay)

    async def async_reset(self) -> None:
        """Reset the stored average state."""
        self.state = AvgState()
        await self.async_save()
