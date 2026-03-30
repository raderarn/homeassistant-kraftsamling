import logging
import aiohttp
import async_timeout
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

class KraftsamlingAPI:
    """ApiClient for Kraftsamling OpenAPI."""

    def __init__(self, api_key: str, session: aiohttp.ClientSession):
        self.api_key = api_key
        self._session = session
        self.base_url = "https://api.kraftsamling.se/v1"

    async def get_facilities(self) -> list:
        """Fetch all utility facilities associated with the account."""
        url = f"{self.base_url}/Anlaggning"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }

        try:
            async with async_timeout.timeout(10):
                response = await self._session.get(url, headers=headers)
                response.raise_for_status()
                return await response.json()
        except Exception as err:
            _LOGGER.error("Failed to fetch facilities from Kraftsamling: %s", err)
            return []

    async def get_consumption_data(self, facility_id: str, start_dt: datetime) -> list:
        """Fetch hourly consumption values from a specific date until now."""
        # Ensure the date format matches the API requirement (ISO8601)
        start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%S")
        
        url = f"{self.base_url}/Anlaggning/{facility_id}/Varden"
        params = {
            "fran": start_str,
            "upplosning": "Timme" 
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }

        try:
            async with async_timeout.timeout(20):
                response = await self._session.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = await response.json()
                
                # Map API response to internal format
                # Adjust 'Tidpunkt' and 'Varde' if the Swagger fields differ
                return [
                    {
                        "timestamp": datetime.fromisoformat(item["Tidpunkt"]),
                        "consumption": float(item["Varde"])
                    }
                    for item in data if item.get("Varde") is not None
                ]
        except Exception as err:
            _LOGGER.warning("Could not fetch values for facility %s: %s", facility_id, err)
            return []
