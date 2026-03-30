import logging
import aiohttp
import async_timeout
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

class KraftsamlingAPI:
    """ApiClient for Dalakraft IO."""

    def __init__(self, api_key: str, session: aiohttp.ClientSession):
        self.api_key = api_key
        self._session = session
        # New Base URL for Dalakraft IO
        self.base_url = "https://io.dalakraft.se/api/v1"

    async def get_facilities(self) -> list:
        """Fetch all billing points (facilities) from Dalakraft IO."""
        url = f"{self.base_url}/BillingPoints"
        headers = {
            "X-API-KEY": self.api_key, # Check if it's X-API-KEY or Bearer in Swagger
            "Accept": "application/json"
        }

        try:
            async with async_timeout.timeout(10):
                response = await self._session.get(url, headers=headers)
                response.raise_for_status()
                data = await response.json()
                # Dalakraft returns a list of billing points. 
                # We need the 'id' (often GUID) for each.
                return data 
        except Exception as err:
            _LOGGER.error("Failed to fetch billing points from Dalakraft: %s", err)
            return []

    async def get_consumption_data(self, billing_point_id: str, start_dt: datetime) -> list:
        """Fetch hourly volumes for a specific billing point."""
        start_str = start_dt.strftime("%Y-%m-%d") # API might prefer YYYY-MM-DD
        
        # Endpoint: /api/v1/BillingPoints/{id}/Volumes
        url = f"{self.base_url}/BillingPoints/{billing_point_id}/Volumes"
        params = {
            "from": start_str,
            "resolution": "Hour" 
        }
        headers = {
            "X-API-KEY": self.api_key,
            "Accept": "application/json"
        }

        try:
            async with async_timeout.timeout(20):
                response = await self._session.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = await response.json()
                
                # Dalakraft IO typically returns: {"date": "...", "value": ...}
                # Check your Swagger 'Response Body' to confirm field names!
                return [
                    {
                        "timestamp": datetime.fromisoformat(item["date"].replace("Z", "+00:00")),
                        "consumption": float(item["value"])
                    }
                    for item in data if item.get("value") is not None
                ]
        except Exception as err:
            _LOGGER.warning("Could not fetch volumes for %s: %s", billing_point_id, err)
            return []
