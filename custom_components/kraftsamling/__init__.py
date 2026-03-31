"""The Kraftsamling integration."""
import logging
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD
from .api import KraftsamlingAPI
from .coordinator import KraftsamlingCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry):
    """Set up Kraftsamling from a config entry."""
    # Use the shared Home Assistant aiohttp session
    session = async_get_clientsession(hass)
    
    # Initialize the API client with stored credentials
    api = KraftsamlingAPI(
        entry.data[CONF_USERNAME], 
        entry.data[CONF_PASSWORD], 
        session
    )
    
    # Initialize the DataUpdateCoordinator. 
    # We pass the entire 'entry' object so the coordinator can access 
    # 'selected_facilities' and 'start_date' from the entry data.
    coordinator = KraftsamlingCoordinator(hass, api, entry)
    
    # Store the coordinator in hass.data to make it accessible to other platforms
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Trigger the first data refresh from the API
    await coordinator.async_config_entry_first_refresh()
    
    return True

async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    # Remove the coordinator from hass.data when the integration is removed
    if entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)
    return True
