"""Sensor platform for Kraftsamling."""
from __future__ import annotations
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the Kraftsamling sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    selected_ids = entry.data.get("selected_facilities", [])
    
    async_add_entities([KraftsamlingEnergySensor(coordinator, eid) for eid in selected_ids])

class KraftsamlingEnergySensor(CoordinatorEntity, SensorEntity):
    """Representation of a Kraftsamling sensor showing last hour consumption."""

    def __init__(self, coordinator, ext_id):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._ext_id = ext_id
        self._attr_unique_id = f"{DOMAIN}_{ext_id}_energy"
        self.entity_id = f"sensor.kraftsamling_energy_{ext_id}"
        self._attr_name = f"Kraftsamling Energy {ext_id}"
        
        # Mandatory attributes to make the sensor selectable in the Energy Dashboard.
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        
        # We use TOTAL_INCREASING so Home Assistant accepts it as a valid energy source.
        # Since the value returned is only the last hour's consumption (not the grand total),
        # there will be no massive spikes in the dashboard.
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> float | None:
        """Return the last hour value from the coordinator."""
        # This returns the single hour value (e.g., 1.2) from the coordinator's data.
        if isinstance(self.coordinator.data, (int, float)) and not isinstance(self.coordinator.data, bool):
            return self.coordinator.data
        return None
