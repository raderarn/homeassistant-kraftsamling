"""Sensor platform for Kraftsamling Integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

# Home Assistant modules for database (recorder) and sensor definitions
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

# Safety Guard: If hourly consumption exceeds this value (kWh), 
# it's interpreted as a measurement error/outlier and set to 0.
# Adjust this based on your main fuse (e.g., 25A @ 230V 3-phase ≈ 17kWh/h).
MAX_PLAUSIBLE_HOURLY_KWH = 50.0

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up sensor entities based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    ids = entry.data.get("selected_facilities", [])
    if not ids:
        return

    # Create a storage for 'mirrors' (statistics reflections) 
    # so multiple sensors can share the same database read operation.
    mirrors = hass.data.setdefault(DOMAIN, {}).setdefault("_stat_mirrors", {})
    entities: list[SensorEntity] = []

    for ext_id in ids:
        stat_id = f"{STATISTICS_ID_BASE}{ext_id}"
        key = f"{entry.entry_id}:{ext_id}"
        
        # If we don't already have a mirror for this facility, create one.
        mirror = mirrors.get(key)
        if mirror is None:
            mirror = _FacilityStatsMirror(hass, stat_id)
            mirrors[key] = mirror

        # Create two sensors per facility: 
        # 1. Total meter reading
        # 2. Consumption for the latest hour
        entities.append(KraftsamlingEnergyTotalSensor(coordinator, ext_id, stat_id, mirror))
        entities.append(KraftsamlingEnergyHourSensor(coordinator, ext_id, stat_id, mirror))

    # Add the created sensors to Home Assistant.
    async_add_entities(entities, True)


class _FacilityStatsMirror:
    """
    Reads imported long-term statistics (sum) from the database 
    and calculates the difference between the latest data points.
    """

    def __init__(self, hass: HomeAssistant, stat_id: str) -> None:
        self.hass = hass
        self.stat_id = stat_id
        self.last_sum: float = 0.0        # Total accumulated sum (kWh)
        self.last_ts: float | None = None   # Timestamp for the latest reading
        self.hour_kwh: float = 0.0        # Calculated consumption for the latest hour
        self.prev_sum: float | None = None
        self.reset_detected: bool = False
        self._unsub = None
        self._listeners: set[callable] = set()

    async def async_register(self, cb) -> None:
        """Register a sensor as a listener and start the update cycle."""
        self._listeners.add(cb)
        if self._unsub is None:
            # Perform an initial read immediately on startup
            await self._refresh()
            # Schedule updates once every hour
            self._unsub = async_track_time_interval(self.hass, self._tick, timedelta(hours=1))

    async def async_unregister(self, cb) -> None:
        """Remove a listener and stop updates if no one is listening anymore."""
        self._listeners.discard(cb)
        if not self._listeners and self._unsub is not None:
            self._unsub()
            self._unsub = None

    async def _tick(self, _now) -> None:
        """Triggered every hour to fetch new statistics."""
        await self._refresh()
        # Notify all connected sensors that the data has changed
        for cb in tuple(self._listeners):
            try:
                cb()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Mirror listener failed for %s", self.stat_id, exc_info=True)

    async def _refresh(self) -> None:
        """Fetches the latest two statistics points from the Home Assistant database."""
        try:
            # We request the latest 2 points ('sum') to calculate the difference (delta).
            stats = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 2, self.stat_id, True, {"sum"}
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Stats read failed for %s: %s", self.stat_id, err)
            return

        # Verify that we actually received data for our statistics ID
        if not stats or self.stat_id not in stats or not stats[self.stat_id]:
            return

        pts = stats[self.stat_id]
        newest = pts[0]  # The most recent point
        s0 = newest.get("sum")
        t0 = newest.get("start")
        if s0 is None:
            return

        s0 = float(s0)
        self.last_sum = s0
        self.last_ts = float(t0) if t0 is not None else self.last_ts

        self.reset_detected = False
        
        # If we have at least two data points, we can calculate the hourly consumption
        if len(pts) >= 2 and pts[1].get("sum") is not None:
            s1 = float(pts[1]["sum"])  # The second most recent point
            diff = s0 - s1
            
            # Logic to handle outliers and resets:
            
            # Case 1: Normal increase (between 0 and our plausibility cap)
            if 0 <= diff < MAX_PLAUSIBLE_HOURLY_KWH:
                self.hour_kwh = diff
                self.prev_sum = s1
            # Case 2: Negative difference (meter reset or replacement)
            elif diff < 0:
                _LOGGER.info("Meter reset detected for %s", self.stat_id)
                self.hour_kwh = 0.0
                self.prev_sum = s1
                self.reset_detected = True
            # Case 3: Unreasonably high increase (outlier/spike)
            else:
                _LOGGER.warning(
                    "Ignoring suspected outlier for %s: %s kWh (Max allowed is %s)", 
                    self.stat_id, diff, MAX_PLAUSIBLE_HOURLY_KWH
                )
                self.hour_kwh = 0.0


class _BaseKraftsamlingMirrorSensor(CoordinatorEntity, SensorEntity):
    """Common base for sensors retrieving data from _FacilityStatsMirror."""

    def __init__(self, coordinator, ext_id: str, stat_id: str, mirror: _FacilityStatsMirror) -> None:
        super().__init__(coordinator)
        self._ext_id = ext_id
        self._stat_id = stat_id
        self._mirror = mirror
        self._mirror_cb = self._on_mirror_update

    async def async_added_to_hass(self) -> None:
        """Called when the sensor is added to HA - register with our mirror."""
        await super().async_added_to_hass()
        await self._mirror.async_register(self._mirror_cb)
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Called when the sensor is removed - unregister."""
        await self._mirror.async_unregister(self._mirror_cb)

    def _on_mirror_update(self) -> None:
        """Callback invoked by the mirror when new statistics have been read."""
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Additional diagnostic information visible in the Home Assistant UI."""
        return {
            "statistic_id": self._stat_id,
            "last_sum": self._mirror.last_sum,
            "last_stat_timestamp": self._mirror.last_ts,
            "last_hour_kwh": self._mirror.hour_kwh,
            "reset_detected": self._mirror.reset_detected,
        }


class KraftsamlingEnergyTotalSensor(_BaseKraftsamlingMirrorSensor):
    """Cumulative energy counter. Recommended for the Energy Dashboard."""

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
        """Return the current total sum."""
        return float(self._mirror.last_sum or 0.0)


class KraftsamlingEnergyHourSensor(_BaseKraftsamlingMirrorSensor):
    """Hourly consumption in kWh. Used for UI graphs and short-term tracking."""

    _attr_device_class = SensorDeviceClass.ENERGY
    # Changed to TOTAL to resolve the "Arithmetic mean" database error.
    # This treats the value as a discrete amount rather than a state to be averaged.
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "kWh"
    _attr_force_update = True

    def __init__(self, coordinator, ext_id: str, stat_id: str, mirror: _FacilityStatsMirror) -> None:
        super().__init__(coordinator, ext_id, stat_id, mirror)
        self._attr_unique_id = f"{DOMAIN}_{ext_id}_energy_hour"
        self.entity_id = f"sensor.kraftsamling_energy_hour_{ext_id}"
        self._attr_name = f"Kraftsamling Energy Hour {ext_id}"

    @property
    def native_value(self) -> float:
        """Return the calculated hourly delta."""
        return float(self._mirror.hour_kwh or 0.0)
