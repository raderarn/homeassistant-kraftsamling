"""Sensor platform for Kraftsamling."""
from __future__ import annotations

import logging
from datetime import timedelta, datetime, timezone
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import get_last_statistics
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATISTICS_ID_BASE

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    ids = entry.data.get("selected_facilities", [])
    if ids: async_add_entities([KraftsamlingEnergySensor(hass, coordinator, ext_id) for ext_id in ids], True)

class KraftsamlingEnergySensor(CoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "kWh"
    _attr_force_update = True

    def __init__(self, hass: HomeAssistant, coordinator, ext_id: str) -> None:
        super().__init__(coordinator)
        self.hass = hass; self._ext_id = ext_id
        self._attr_unique_id = f"{DOMAIN}_{ext_id}_energy"
        self.entity_id = f"sensor.kraftsamling_energy_{ext_id}"
        self._attr_name = f"Kraftsamling Energy {ext_id}"
        self._stat_id = f"{STATISTICS_ID_BASE}{ext_id}"
        self._val: float | None = None; self._last_sum: float | None = None; self._last_ts: float | None = None
        self._unsub = None

    @property
    def native_value(self) -> float | None: return self._val

    @property
    def last_reset(self):
        if self._last_ts is None:
            return None
        return datetime.fromtimestamp(self._last_ts, tz=timezone.utc)
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"statistic_id": self._stat_id, "last_sum": self._last_sum, "last_stat_timestamp": self._last_ts}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._refresh()
        self._unsub = async_track_time_interval(self.hass, self._tick, timedelta(hours=1))

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub: self._unsub(); self._unsub = None

    async def _tick(self, _now) -> None:
        await self._refresh()
        self.async_write_ha_state()

    async def _refresh(self) -> None:
        try:
            stats = await get_instance(self.hass).async_add_executor_job(get_last_statistics, self.hass, 2, self._stat_id, True, {"sum"})
        except Exception as err:
            _LOGGER.debug("Stats read failed for %s: %s", self._stat_id, err); return
        if not stats or self._stat_id not in stats or not stats[self._stat_id]: return
        pts = stats[self._stat_id]; newest = pts[0]; s0 = newest.get("sum"); t0 = newest.get("start")
        if s0 is None: return
        self._last_sum = float(s0); self._last_ts = float(t0) if t0 is not None else None
        if len(pts) >= 2 and pts[1].get("sum") is not None:
            d = float(s0) - float(pts[1]["sum"])
            if d >= 0: self._val = d
