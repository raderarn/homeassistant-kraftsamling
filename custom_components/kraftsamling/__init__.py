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
    
    # Registrera lyssnare för Options Flow (kugghjulet)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Använd delad aiohttp-session från Home Assistant
    session = async_get_clientsession(hass)
    
    # Initiera API-klienten med dina konstanter från const.py
    api = KraftsamlingAPI(
        entry.data.get(CONF_USERNAME), 
        entry.data.get(CONF_PASSWORD), 
        session
    )
    
    # Initiera koordinatören som hanterar datahämtningen
    coordinator = KraftsamlingCoordinator(hass, api, entry)
    
    # Spara koordinatören i hass.data för åtkomst från sensor-plattformen
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Kör den första datahämtningen direkt vid start
    await coordinator.async_config_entry_first_refresh()
    
    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Hantera omladdning när inställningar ändras via Options Flow."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Stäng ner integrationen snyggt."""
    if entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)
    return True
