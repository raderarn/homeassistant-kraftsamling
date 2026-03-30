import voluptuous as vol
from homeassistant import config_entries
# Import the new constants we defined in const.py
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_START_DATE

class KraftsamlingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kraftsamling (Dalakraft IO)."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial setup step when a user adds the integration."""
        errors = {}

        if user_input is not None:
            # Create the entry with the provided credentials
            return self.async_create_entry(
                title=f"Kraftsamling ({user_input[CONF_USERNAME]})", 
                data=user_input
            )

        # Define the form fields the user sees in the Home Assistant UI
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_START_DATE, default="2023-01-01"): str,
            }),
            errors=errors,
        )
