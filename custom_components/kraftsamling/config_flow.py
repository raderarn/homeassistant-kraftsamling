"""Config flow for Kraftsamling."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_START_DATE
from .api import KraftsamlingAPI

_LOGGER = logging.getLogger(__name__)

class KraftsamlingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kraftsamling."""
    VERSION = 1

    def __init__(self):
        """Initialize flow."""
        self._data = {}

    async def async_step_user(self, user_input=None):
        """Initial step to get credentials from user."""
        if user_input is not None:
            self._data = user_input
            return await self.async_step_select_facilities()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_START_DATE, default="2024-01-01"): str,
            }),
        )

    async def async_step_select_facilities(self, user_input=None):
        """Step 2: Authenticate and let user select facilities."""
        session = async_get_clientsession(self.hass)
        
        # Vi använder datan vi fick i steg 1
        api = KraftsamlingAPI(
            self._data[CONF_USERNAME], 
            self._data[CONF_PASSWORD], 
            session
        )
        
        facilities = await api.get_facilities()
        if not facilities:
            return self.async_abort(reason="no_facilities")
        
        # Skapa lista för val i UI
        facility_options = {
            f["externalId"]: f"{f.get('installationAddress', 'Okänd')} ({f['externalId']})" 
            for f in facilities
        }

        if user_input is not None:
            self._data["selected_facilities"] = user_input["facilities"]
            return self.async_create_entry(
                title=f"Kraftsamling ({self._data[CONF_USERNAME]})", 
                data=self._data
            )

        return self.async_show_form(
            step_id="select_facilities",
            data_schema=vol.Schema({
                vol.Required("facilities"): cv.multi_select(facility_options)
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return KraftsamlingOptionsFlowHandler(config_entry)


class KraftsamlingOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow to update credentials via the cogwheel."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            # Uppdatera config entry data med nya värden
            new_data = {**self.config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data={})

        # Hämta nuvarande värden för förifyllnad
        d = self.config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME, default=d.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD, default=d.get(CONF_PASSWORD, "")): str,
                vol.Required(CONF_START_DATE, default=d.get(CONF_START_DATE, "")): str,
            }),
        )
