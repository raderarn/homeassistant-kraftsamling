g"""Sensor platform for Kraftsamling."""
from __future__ import annotations
from homeassistant.components.sensor import SensorEntity
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
        
        # Vi tar bort ENERGY och TOTAL_INCREASING för att undvika spikar i dashboarden.
        # Statistiken sköts nu helt via coordinatorns bakgrundsjobb.
        self._attr_device_class = None
        self._attr_state_class = None
        self._attr_native_unit_of_measurement = "kWh"

    @property
    def native_value(self) -> float | None:
        """Return the last hour value from the coordinator."""
        # Detta returnerar nu värdet från return-satsen i coordinatorn (last_hour_consumption)
        if isinstance(self.coordinator.data, (int, float)) and not isinstance(self.coordinator.data, bool):
            return self.coordinator.data
        return None
