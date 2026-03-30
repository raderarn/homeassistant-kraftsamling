import voluptuous as vol
from datetime import datetime
from homeassistant import config_entries
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_START_DATE

class KraftsamlingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kraftsamling."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(
                title=f"Kraftsamling ({user_input[CONF_USERNAME]})", 
                data=user_input
            )

        # Dynamiskt datum: första dagen i nuvarande månad
        default_date = datetime.now().replace(day=1).strftime("%Y-%m-%d")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                # VIKTIGT: Namnen här (CONF_USERNAME etc) måste matcha nycklarna i din sv.json
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_START_DATE, default=default_date): str,
            }),
            errors=errors,
        )
