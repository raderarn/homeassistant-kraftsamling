"""Config flow for Kraftsamling."""
import logging
from datetime import datetime
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_START_DATE
from .api import KraftsamlingAPI

_LOGGER = logging.getLogger(__name__)

def get_default_start_date():
    """Get the first day of the current month as a string."""
    return datetime.now().replace(day=1).strftime("%Y-%m-%d")

class KraftsamlingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kraftsamling."""
    VERSION = 1

    def __init__(self):
        """Initialize flow."""
        self._data = {}

    async def async_step_user(self, user_input=None):
        """Initial step to get credentials and start date."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()
            self._data = user_input
            return await self.async_step_select_facilities()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_START_DATE, default=get_default_start_date()): str,
            }),
        )

    async def async_step_select_facilities(self, user_input=None):
        """Step 2: Select billing points (facilities)."""
        session = async_get_clientsession(self.hass)
        api = KraftsamlingAPI(session, self._data[CONF_USERNAME], self._data[CONF_PASSWORD])
        
        try:
            facilities = await api.async_get_billingpoints()
        except Exception as err:
            _LOGGER.error("Could not fetch billing points: %s", err)
            return self.async_abort(reason="cannot_connect")
        
        if not facilities:
            return self.async_abort(reason="no_facilities")
        
        facility_options = {
            f["externalId"]: f"{f.get('installationAddress', 'Unknown')} ({f['externalId']})" 
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
        """Get the options flow."""
        return KraftsamlingOptionsFlowHandler(config_entry)


class KraftsamlingOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow (Cogwheel settings)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            # Update the main config entry data with new inputs
            new_data = {**self.config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            
            # Reload the integration to apply changes immediately
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        conf = self.config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME, default=conf.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD, default=conf.get(CONF_PASSWORD, "")): str,
                vol.Required(CONF_START_DATE, default=conf.get(CONF_START_DATE, get_default_start_date())): str,
            }),
        )
