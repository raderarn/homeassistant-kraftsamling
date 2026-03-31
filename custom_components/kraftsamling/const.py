"""Constants for the Kraftsamling integration."""

DOMAIN = "kraftsamling"

# Configuration constants
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_START_DATE = "start_date"

# Base ID for long-term statistics.
# Must start with sensor.DOMAIN_ to be accepted by Home Assistant.
STATISTICS_ID_BASE = "kraftsamling:consumption_"
