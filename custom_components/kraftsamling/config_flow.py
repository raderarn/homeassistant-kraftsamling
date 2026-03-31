import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_START_DATE
from .api import KraftsamlingAPI

class KraftsamlingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kraftsamling."""
    VERSION = 1

    def __init__(self):
        """Initialize flow."""
        self._username = None
        self._password = None
        self._start_date = None

    async def async_step_user(self, user_input=None):
        """Step 1: Get credentials."""
        errors = {}
        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]
            self._start_date = user_input[CONF_START_DATE]
            
            # Testa anslutningen och gå till nästa steg
            return await self.async_step_select_facilities()

        default_date = "2024-01-01" # Eller din dynamiska logik

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_START_DATE, default=default_date): str,
            }),
            errors=errors,
        )

    async def async_step_select_facilities(self, user_input=None):
        """Step 2: Let user select facilities."""
        errors = {}
        session = async_get_clientsession(self.hass)
        api = KraftsamlingAPI(self._username, self._password, session)

        try:
            facilities = await api.get_facilities()
            if not facilities:
                return self.async_abort(reason="no_facilities")
            
            # Skapa en lista för UI:t (Visa adress eller ID)
            facility_options = {
                f["externalId"]: f"{f.get('installationAddress', 'Okänd adress')} ({f['externalId']})"
                for f in facilities
            }

            if user_input is not None:
                return self.async_create_entry(
                    title="Kraftsamling",
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
        except Exception:
            return self.async_abort(reason="cannot_connect")
