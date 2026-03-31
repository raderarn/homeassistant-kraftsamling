"""The Kraftsamling integration."""
import logging
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD
from .api import KraftsamlingAPI
from .coordinator import KraftsamlingCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kraftsamling from a config entry."""
    
    # KORRIGERAD RAD: Metoden heter add_update_listener
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Use the shared Home Assistant aiohttp session
    session = async_get_clientsession(hass)
    
    # Initialize the API client with stored credentials
    api = KraftsamlingAPI(
        entry.data[CONF_USERNAME], 
        entry.data[CONF_PASSWORD], 
        session
    )
    
    # Initialize the DataUpdateCoordinator
    coordinator = KraftsamlingCoordinator(hass, api, entry)
    
    # Store the coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Trigger the first data refresh from the API
    await coordinator.async_config_entry_first_refresh()
    
    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update - reloads the integration."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)
    return True
