"""Sensor platform for Kraftsamling."""
from __future__ import annotations
from homeassistant.components.sensor import SensorEntity, SensorStateClass
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
        
        # We set state_class to MEASUREMENT to satisfy Home Assistant's 
        # statistics engine while avoiding Energy Dashboard spikes.
        self._attr_state_class = SensorStateClass.MEASUREMENT
        
        # We keep device_class as None to prevent the Energy Dashboard from 
        # using the live sensor value for its automatic calculations.
        self._attr_device_class = None
        self._attr_native_unit_of_measurement = "kWh"

    @property
    def native_value(self) -> float | None:
        """Return the last hour value from the coordinator."""
        # This returns the value from the coordinator's return statement (last_hour_consumption)
        if isinstance(self.coordinator.data, (int, float)) and not isinstance(self.coordinator.data, bool):
            return self.coordinator.data
        return None
