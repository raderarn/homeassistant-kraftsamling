import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

# Vi importerar konstanterna direkt för att undvika KeyError
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_START_DATE
from .api import KraftsamlingAPI

_LOGGER = logging.getLogger(__name__)

class KraftsamlingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kraftsamling."""
    VERSION = 1

    def __init__(self):
        """Initialize flow."""
        self._username = None
        self._password = None
        self._start_date = None

    async def async_step_user(self, user_input=None):
        """Step 1: Get credentials from user."""
        errors = {}
        if user_input is not None:
            self._username = user_input.get(CONF_USERNAME)
            self._password = user_input.get(CONF_PASSWORD)
            self._start_date = user_input.get(CONF_START_DATE)
            return await self.async_step_select_facilities()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_START_DATE, default="2024-01-01"): str,
            }),
            errors=errors,
        )

    async def async_step_select_facilities(self, user_input=None):
        """Step 2: Authenticate and let user select facilities."""
        session = async_get_clientsession(self.hass)
        api = KraftsamlingAPI(self._username, self._password, session)

        try:
            facilities = await api.get_facilities()
            if not facilities:
                return self.async_abort(reason="no_facilities")
            
            facility_options = {
                f["externalId"]: f"{f.get('installationAddress', 'Okänd adress')} ({f['externalId']})"
                for f in facilities
            }

            if user_input is not None:
                return self.async_create_entry(
                    title=f"Kraftsamling ({self._username})",
                    data={
                        CONF_USERNAME: self._username,
                        CONF_PASSWORD: self._password,
                        CONF_START_DATE: self._start_date,
                        "selected_facilities": user_input["facilities"]
                    },
                )

            return self.async_show_form(
                step_id="select_facilities",
                data_schema=vol.Schema({
                    vol.Required("facilities"): cv.multi_select(facility_options)
                }),
            )

        except Exception as err:
            _LOGGER.error("Connection error during config flow: %s", err)
            return self.async_abort(reason="cannot_connect")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return KraftsamlingOptionsFlowHandler(config_entry)


class KraftsamlingOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow to update credentials."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            # Skapa en kopia av existerande data och uppdatera med input
            new_data = dict(self.config_entry.data)
            new_data.update(user_input)
            
            # Spara ner den uppdaterade datan till ConfigEntry
            self.hass.config_entries.async_update_entry(
                self.config_entry, 
                data=new_data
            )
            # returnera tom data till options för att stänga flödet
            return self.async_create_entry(title="", data={})

        # Hämta nuvarande värden säkert
        curr_user = self.config_entry.data.get(CONF_USERNAME, "")
        curr_pass = self.config_entry.data.get(CONF_PASSWORD, "")
        curr_start = self.config_entry.data.get(CONF_START_DATE, "2024-01-01")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME, default=curr_user): str,
                vol.Required(CONF_PASSWORD, default=curr_pass): str,
                vol.Required(CONF_START_DATE, default=curr_start): str,
            }),
        )
