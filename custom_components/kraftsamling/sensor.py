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
    if not ids:
        return

    mirrors = hass.data.setdefault(DOMAIN, {}).setdefault("_stat_mirrors", {})
    entities: list[SensorEntity] = []

    for ext_id in ids:
        stat_id = f"{STATISTICS_ID_BASE}{ext_id}"
        key = f"{entry.entry_id}:{ext_id}"
        mirror = mirrors.get(key)
        if mirror is None:
            mirror = _FacilityStatsMirror(hass, stat_id)
            mirrors[key] = mirror

        entities.append(KraftsamlingEnergyTotalSensor(coordinator, ext_id, stat_id, mirror))
        entities.append(KraftsamlingEnergyHourSensor(coordinator, ext_id, stat_id, mirror))

    async_add_entities(entities, True)


class _FacilityStatsMirror:
    """Reads imported statistics (sum) and exposes cached values to sensor entities."""

    def __init__(self, hass: HomeAssistant, stat_id: str) -> None:
        self.hass = hass
        self.stat_id = stat_id
        self.last_sum: float = 0.0
        self.last_ts: float | None = None
        self.hour_kwh: float = 0.0
        self.prev_sum: float | None = None
        self.reset_detected: bool = False
        self._unsub = None
        self._listeners: set[callable] = set()

    async def async_register(self, cb) -> None:
        self._listeners.add(cb)
        if self._unsub is None:
            await self._refresh()
            self._unsub = async_track_time_interval(self.hass, self._tick, timedelta(hours=1))

    async def async_unregister(self, cb) -> None:
        self._listeners.discard(cb)
        if not self._listeners and self._unsub is not None:
            self._unsub()
            self._unsub = None

    async def _tick(self, _now) -> None:
        await self._refresh()
        for cb in tuple(self._listeners):
            try:
                cb()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Mirror listener failed for %s", self.stat_id, exc_info=True)

    async def _refresh(self) -> None:
        try:
            stats = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 2, self.stat_id, True, {"sum"}
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Stats read failed for %s: %s", self.stat_id, err)
            return

        if not stats or self.stat_id not in stats or not stats[self.stat_id]:
            return

        pts = stats[self.stat_id]
        newest = pts[0]
        s0 = newest.get("sum")
        t0 = newest.get("start")
        if s0 is None:
            return

        s0 = float(s0)
        self.last_sum = s0
        self.last_ts = float(t0) if t0 is not None else self.last_ts

        self.reset_detected = False
        if len(pts) >= 2 and pts[1].get("sum") is not None:
            s1 = float(pts[1]["sum"])
            d = s0 - s1
            if d >= 0:
                self.hour_kwh = d
                self.prev_sum = s1
            else:
                # Sum went backwards -> likely reset/meter cycle.
                # Keep sensors alive and show 0 for the hour.
                self.hour_kwh = 0.0
                self.prev_sum = s1
                self.reset_detected = True


class _BaseKraftsamlingMirrorSensor(CoordinatorEntity, SensorEntity):
    """Base for sensors backed by _FacilityStatsMirror."""

    def __init__(self, coordinator, ext_id: str, stat_id: str, mirror: _FacilityStatsMirror) -> None:
        super().__init__(coordinator)
        self._ext_id = ext_id
        self._stat_id = stat_id
        self._mirror = mirror
        self._mirror_cb = self._on_mirror_update

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._mirror.async_register(self._mirror_cb)
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        await self._mirror.async_unregister(self._mirror_cb)

    def _on_mirror_update(self) -> None:
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "statistic_id": self._stat_id,
            "last_sum": self._mirror.last_sum,
            "last_stat_timestamp": self._mirror.last_ts,
            "last_hour_kwh": self._mirror.hour_kwh,
            "reset_detected": self._mirror.reset_detected,
        }


class KraftsamlingEnergyTotalSensor(_BaseKraftsamlingMirrorSensor):
    """Cumulative energy counter. Use THIS in Energy Dashboard."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "kWh"
    _attr_force_update = True

    def __init__(self, coordinator, ext_id: str, stat_id: str, mirror: _FacilityStatsMirror) -> None:
        super().__init__(coordinator, ext_id, stat_id, mirror)
        self._attr_unique_id = f"{DOMAIN}_{ext_id}_energy_total"
        self.entity_id = f"sensor.kraftsamling_energy_total_{ext_id}"
        self._attr_name = f"Kraftsamling Energy Total {ext_id}"

    @property
    def native_value(self) -> float:
        # Always numeric to avoid unavailable
        return float(self._mirror.last_sum or 0.0)

    @property
    def last_reset(self):
        # Not needed for total_increasing
        return None


class KraftsamlingEnergyHourSensor(_BaseKraftsamlingMirrorSensor):
    """Hourly consumption in kWh. Use for UI graphs (small values, no huge max)."""

    # Intentionally NOT device_class ENERGY so it won't be treated as an energy source in the Energy dashboard dropdown.
    _attr_device_class = None
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "kWh"
    _attr_force_update = True

    def __init__(self, coordinator, ext_id: str, stat_id: str, mirror: _FacilityStatsMirror) -> None:
        super().__init__(coordinator, ext_id, stat_id, mirror)
        self._attr_unique_id = f"{DOMAIN}_{ext_id}_energy_hour"
        self.entity_id = f"sensor.kraftsamling_energy_hour_{ext_id}"
        self._attr_name = f"Kraftsamling Energy Hour {ext_id}"

    @property
    def native_value(self) -> float:
        # Always numeric to avoid unavailable
        return float(self._mirror.hour_kwh or 0.0)
