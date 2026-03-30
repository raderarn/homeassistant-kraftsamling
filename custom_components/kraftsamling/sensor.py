"""Sensor platform for Kraftsamling (placeholder)."""
from __future__ import annotations
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """
    No physical entities are created as we use async_import_statistics.
    This file is required for the integration to be recognized as a sensor platform.
    """
    return
