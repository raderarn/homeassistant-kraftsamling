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

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Kraftsamling sensors."""
    # Fetch the coordinator from hass.data
    coordinator = hass.data[DOMAIN][entry.entry_id]
    selected_ids = entry.data.get("selected_facilities", [])
    
    # Create a sensor for each selected facility
    entities = [
        KraftsamlingEnergySensor(coordinator, ext_id)
        for ext_id in selected_ids
    ]
    async_add_entities(entities)

class KraftsamlingEnergySensor(CoordinatorEntity, SensorEntity):
    """Representation of a Kraftsamling energy sensor."""

    def __init__(self, coordinator, ext_id):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._ext_id = ext_id
        
        # This unique_id links the entity to the integration
        self._attr_unique_id = f"{DOMAIN}_{ext_id}_energy"
        
        # CRITICAL: This entity_id MUST match the statistic_id prefix you used
        # If your statistics use 'sensor.kraftsamling_energy_...', this must match.
        self.entity_id = f"sensor.kraftsamling_energy_{ext_id}"
        
        self._attr_name = f"Kraftsamling Energy {ext_id}"
        
        # Required attributes for the Energy Dashboard
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    @property
    def native_value(self) -> float | None:
        """Return the last known sum from the coordinator."""
        # Vi letar i coordinatorns interna minne efter det senaste sum-värdet
        if hasattr(self.coordinator, "last_sum"):
            return self.coordinator.last_sum
        return None
