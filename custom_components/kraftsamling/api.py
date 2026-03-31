"""API client for Kraftsamling (Dalakraft IO)."""
import logging
import asyncio
from datetime import datetime
import aiohttp

_LOGGER = logging.getLogger(__name__)

class KraftsamlingAPI:
    """Client to communicate with the Dalakraft IO API."""

    def __init__(self, customer_id: str, api_key: str, session: aiohttp.ClientSession):
        """Initialize the API client."""
        self.customer_id = str(customer_id).strip()
        self.api_key = str(api_key).strip()
        self.session = session
        self.base_url = "https://io.dalakraft.se"

    async def _make_request(self, method: str, url: str, json_payload=None) -> list | dict:
        """Make an async HTTP request to the API."""
        headers = {
            "X-Customer-Id": self.customer_id,
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            async with self.session.request(
                method, url, headers=headers, json=json_payload, timeout=20
            ) as response:
                if response.status == 401:
                    _LOGGER.error("Authentication failed (401) for URL: %s. Payload was: %s", url, json_payload)
                    return []
                
                response.raise_for_status()
                return await response.json()

        except Exception as err:
            _LOGGER.error("Error connecting to Dalakraft API (%s): %s", url, err)
            return []

    async def get_facilities(self) -> list:
        """Fetch all billing points (facilities) for the customer."""
        url = f"{self.base_url}/Billingpoints"
        data = await self._make_request("GET", url)
        
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("billingpoints", [])
        return []

    async def get_consumption_data(self, external_id: str, start_dt: datetime) -> list:
        """Fetch hourly consumption volumes via POST request."""
        url = f"{self.base_url}/Billingpoints/volumes"
        end_dt = datetime.now()
        
        # SÄKERSTÄLL STRÄNG: Vi tvingar ID att vara sträng för att undvika 401
        payload = {
            "billingpoints": [str(external_id)],
            "resolution": "hour",
            "periodStart": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "periodEnd": end_dt.strftime("%Y-%m-%dT%H:%M:%S")
        }

        try:
            data = await self._make_request("POST", url, json_payload=payload)
            _LOGGER.debug("RAW API RESPONSE: %s", data)
            
            consumptions = []
            if isinstance(data, list) and len(data) > 0:
                consumptions = data[0].get("consumptions", [])
            elif isinstance(data, dict):
                consumptions = data.get("consumptions", [])

            results = []
            for item in consumptions:
                quantity = item.get("quantity")
                start_time = item.get("periodStart")
                if quantity is not None and start_time:
                    ts_str = start_time.replace("Z", "+00:00")
                    results.append({
                        "timestamp": datetime.fromisoformat(ts_str),
                        "consumption": float(quantity)
                    })
            
            _LOGGER.debug("Fetched %s consumption records for %s", len(results), external_id)
            return results

        except Exception as err:
            _LOGGER.warning("Could not fetch volumes for %s: %s", external_id, err)
            return []
