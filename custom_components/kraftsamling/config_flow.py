import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]
            self._start_date = user_input[CONF_START_DATE]
            
            # Gå vidare till att hämta anläggningar
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
        errors = {}
        session = async_get_clientsession(self.hass)
        api = KraftsamlingAPI(self._username, self._password, session)

        try:
            # Här sker anslutningen och token-hämtningen
            facilities = await api.get_facilities()
            
            if not facilities:
                _LOGGER.error("No facilities found for user %s", self._username)
                return self.async_abort(reason="no_facilities")
            
            # Skapa lista för UI:t. Vi använder externalId som nyckel.
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
                    vol.Required("facilities"): vol.All(
                        vol.Subset(facility_options), vol.Length(min=1)
                    )
                }),
            )

        except Exception as err:
            _LOGGER.error("Connection error during config flow: %s", err)
            # Om det skiter sig här får du "cannot_connect"
            return self.async_abort(reason="cannot_connect")
