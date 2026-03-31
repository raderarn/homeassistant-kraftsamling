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
    
    # Register listener for Options Flow (the gear icon) updates
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Use Home Assistant's shared aiohttp session
    session = async_get_clientsession(hass)
    
    # CORRECTED: Order must be session, username, password 
    # to match KraftsamlingAPI.__init__
    api = KraftsamlingAPI(
        session,
        entry.data.get(CONF_USERNAME), 
        entry.data.get(CONF_PASSWORD)
    )
    
    # Initialize the coordinator which manages data fetching
    coordinator = KraftsamlingCoordinator(hass, api, entry)
    
    # Store the coordinator in hass.data for access from other platforms (e.g. sensor)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Perform the first data refresh immediately during startup
    await coordinator.async_config_entry_first_refresh()
    
    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle reloading when settings are changed via Options Flow."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration and clean up."""
    if entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)
    return True
