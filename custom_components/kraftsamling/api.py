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

    async def _make_request(self, method: str, url: str, json_payload=None):
        """Make an async HTTP request with Swagger-mimicking headers."""
        headers = {
            "X-Customer-Id": self.customer_id,
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        }

        try:
            async with self.session.request(
                method, url, headers=headers, json=json_payload, timeout=30
            ) as response:
                if response.status == 401:
                    _LOGGER.error("Auth failed (401) for %s. Check credentials.", url)
                    return []
                
                response.raise_for_status()
                return await response.json()
        except Exception as err:
            _LOGGER.error("Error connecting to %s: %s", url, err)
            return []

    async def get_facilities(self) -> list:
        """Fetch all billing points (facilities)."""
        url = f"{self.base_url}/Billingpoints"
        data = await self._make_request("GET", url)
        if isinstance(data, list):
            return data
        return data.get("billingpoints", []) if isinstance(data, dict) else []

    async def get_consumption_data(self, external_id: str, start_dt: datetime) -> list:
        """Fetch hourly consumption volumes."""
        url = f"{self.base_url}/Billingpoints/volumes"
        
        # Dalakraft kräver ID som sträng i en lista
        payload = {
            "billingpoints": [str(external_id)],
            "resolution": "hour",
            "periodStart": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "periodEnd": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        }

        data = await self._make_request("POST", url, json_payload=payload)
        
        consumptions = []
        if isinstance(data, list) and len(data) > 0:
            consumptions = data[0].get("consumptions", [])
        elif isinstance(data, dict):
            consumptions = data.get("consumptions", [])

        results = []
        for item in consumptions:
            if "quantity" in item and "periodStart" in item:
                ts_str = item["periodStart"].replace("Z", "+00:00")
                results.append({
                    "timestamp": datetime.fromisoformat(ts_str),
                    "consumption": float(item["quantity"])
                })
        return results
