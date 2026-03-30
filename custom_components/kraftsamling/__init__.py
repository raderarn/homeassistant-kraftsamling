"""The Kraftsamling integration."""
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_START_DATE
from .api import KraftsamlingAPI
from .coordinator import KraftsamlingCoordinator

async def async_setup_entry(hass, entry):
    """Set up Kraftsamling from a config entry."""
    session = async_get_clientsession(hass)
    
    # We now pass both Username and Password to the API client
    api = KraftsamlingAPI(
        entry.data[CONF_USERNAME], 
        entry.data[CONF_PASSWORD], 
        session
    )
    
    coordinator = KraftsamlingCoordinator(hass, api, entry.data[CONF_START_DATE])
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Trigger the first data refresh
    await coordinator.async_config_entry_first_refresh()
    
    return True

async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    return True
