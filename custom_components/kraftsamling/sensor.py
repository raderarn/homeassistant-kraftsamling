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
# it's interpreted as a measurement error/spike and suppressed.
MAX_PLAUSIBLE_HOURLY_KWH = 50.0

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up sensor entities based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    ids = entry.data.get("selected_facilities", [])
    if not ids:
        return

    # Use a shared 'mirror' storage to prevent redundant database queries 
    # when multiple sensors need the same statistical data.
    mirrors = hass.data.setdefault(DOMAIN, {}).setdefault("_stat_mirrors", {})
    entities: list[SensorEntity] = []

    for ext_id in ids:
        stat_id = f"{STATISTICS_ID_BASE}{ext_id}"
        key = f"{entry.entry_id}:{ext_id}"
        
        # Initialize a mirror for this specific facility if it doesn't exist.
        mirror = mirrors.get(key)
        if mirror is None:
            mirror = _FacilityStatsMirror(hass, stat_id)
            mirrors[key] = mirror

        # Create both the cumulative 'Total' sensor and the delta 'Hour' sensor.
        entities.append(KraftsamlingEnergyTotalSensor(coordinator, ext_id, stat_id, mirror))
        entities.append(KraftsamlingEnergyHourSensor(coordinator, ext_id, stat_id, mirror))

    # Register the entities within Home Assistant.
    async_add_entities(entities, True)


class _FacilityStatsMirror:
    """
    Acts as a data bridge, fetching long-term statistics from the recorder
    and calculating the difference between points to derive hourly consumption.
    """

    def __init__(self, hass: HomeAssistant, stat_id: str) -> None:
        self.hass = hass
        self.stat_id = stat_id
        self.last_sum: float = 0.0        # Most recent total sum (kWh)
        self.last_ts: float | None = None   # Timestamp of the newest data point
        self.hour_kwh: float = 0.0        # Calculated kWh consumed in the last interval
        self.prev_sum: float | None = None
        self.reset_detected: bool = False
        self._unsub = None
        self._listeners: set[callable] = set()

    async def async_register(self, cb) -> None:
        """Register a sensor callback and start the polling interval."""
        self._listeners.add(cb)
        if self._unsub is None:
            # Fetch data immediately on first registration
            await self._refresh()
            # Polling interval set to 1 hour to match typical statistics resolution
            self._unsub = async_track_time_interval(self.hass, self._tick, timedelta(hours=1))

    async def async_unregister(self, cb) -> None:
        """Unregister a callback and stop polling if no sensors are active."""
        self._listeners.discard(cb)
        if not self._listeners and self._unsub is not None:
            self._unsub()
            self._unsub = None

    async def _tick(self, _now) -> None:
        """Periodic task to refresh statistics and notify sensors."""
        await self._refresh()
        for cb in tuple(self._listeners):
            try:
                cb()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Mirror listener update failed for %s", self.stat_id, exc_info=True)

    async def _refresh(self) -> None:
        """Fetch the latest two sum-based statistics from the database."""
        try:
            stats = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 2, self.stat_id, True, {"sum"}
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed to read stats for %s: %s", self.stat_id, err)
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
        
        # Calculate the delta (diff) if we have two consecutive data points
        if len(pts) >= 2 and pts[1].get("sum") is not None:
            s1 = float(pts[1]["sum"])
            diff = s0 - s1
            
            # Logic to handle spikes and counter resets:
            if 0 <= diff < MAX_PLAUSIBLE_HOURLY_KWH:
                self.hour_kwh = diff
                self.prev_sum = s1
            elif diff < 0:
                # Meter reset or rollover detected
                _LOGGER.info("Counter reset detected for %s", self.stat_id)
                self.hour_kwh = 0.0
                self.prev_sum = s1
                self.reset_detected = True
            else:
                # Value is higher than physically possible; likely a database anomaly
                _LOGGER.warning(
                    "Suppressed outlier for %s: %s kWh (Threshold: %s)", 
                    self.stat_id, diff, MAX_PLAUSIBLE_HOURLY_KWH
                )
                self.hour_kwh = 0.0


class _BaseKraftsamlingMirrorSensor(CoordinatorEntity, SensorEntity):
    """Common logic for sensors that update based on the mirror data."""

    def __init__(self, coordinator, ext_id: str, stat_id: str, mirror: _FacilityStatsMirror) -> None:
        super().__init__(coordinator)
        self._ext_id = ext_id
        self._stat_id = stat_id
        self._mirror = mirror
        self._mirror_cb = self._on_mirror_update

    async def async_added_to_hass(self) -> None:
        """Register with the mirror when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        await self._mirror.async_register(self._mirror_cb)
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup registration on removal."""
        await self._mirror.async_unregister(self._mirror_cb)

    def _on_mirror_update(self) -> None:
        """Trigger state update in HA when the mirror pulls new data."""
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose diagnostic data in the entity attributes."""
        return {
            "statistic_id": self._stat_id,
            "last_sum": self._mirror.last_sum,
            "last_stat_timestamp": self._mirror.last_ts,
            "last_hour_kwh": self._mirror.hour_kwh,
            "reset_detected": self._mirror.reset_detected,
        }


class KraftsamlingEnergyTotalSensor(_BaseKraftsamlingMirrorSensor):
    """Cumulative sensor for the Energy Dashboard (Total Increasing)."""

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
        """Return the current cumulative sum."""
        return float(self._mirror.last_sum or 0.0)


class KraftsamlingEnergyHourSensor(_BaseKraftsamlingMirrorSensor):
    """Hourly consumption sensor using 'Measurement' to avoid database conflicts."""

    # We set device_class to None to prevent Home Assistant from enforcing 
    # 'sum' statistics which conflict with existing 'mean' data points.
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
        """Return the calculated hourly value."""
        return float(self._mirror.hour_kwh or 0.0)
