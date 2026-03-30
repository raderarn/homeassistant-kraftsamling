import logging
import aiohttp
import async_timeout
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

class KraftsamlingAPI:
    """API client for Dalakraft IO electricity data."""

    def __init__(self, username, password, session: aiohttp.ClientSession):
        """Initialize the API client."""
        self.username = username
        self.password = password
        self._session = session
        self.base_url = "https://io.dalakraft.se"
        self._token = None

    async def _async_get_token(self):
        """Authenticate with the service and retrieve a bearer token."""
        url = f"{self.base_url}/Auth"
        payload = {"User": self.username, "password": self.password}
        
        async with async_timeout.timeout(10):
            response = await self._session.post(url, json=payload)
            response.raise_for_status()
            res_data = await response.json()
            
            # Extract the authorization token from the response structure
            token_info = res_data.get("tokenUsers", {})
            self._token = token_info.get("authToken")
            
        if not self._token:
            _LOGGER.error("Authentication failed: No authToken found in response")
            raise Exception("Access denied")

    async def get_facilities(self) -> list:
        """Fetch all billing points associated with the user account."""
        if not self._token:
            await self._async_get_token()

        url = f"{self.base_url}/Billingpoints"
        headers = {"Authorization": self._token}

        async with async_timeout.timeout(10):
            response = await self._session.get(url, headers=headers)
            
            # Handle token expiration (re-authenticate if 401 Unauthorized)
            if response.status == 401:
                await self._async_get_token()
                headers["Authorization"] = self._token
                response = await self._session.get(url, headers=headers)
            
            response.raise_for_status()
            data = await response.json()
            
            # Return the list of available billing points
            return data.get("billingPoints", [])

    async def get_consumption_data(self, external_id: str, start_dt: datetime) -> list:
        """Fetch hourly consumption volumes for a specific billing point."""
        if not self._token:
            await self._async_get_token()

        url = f"{self.base_url}/Billingpoints/volumes"
        end_dt = datetime.now()
        
        # Define the request payload for hourly resolution
        payload = {
            "billingpoints": [external_id],
            "resolution": "hour",
            "periodStart": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "periodEnd": end_dt.strftime("%Y-%m-%dT%H:%M:%S")
        }
        
        headers = {"Authorization": self._token}

        async with async_timeout.timeout(20):
            response = await self._session.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = await response.json()
            
            # Process consumption entries and format for Home Assistant
            consumptions = data.get("consumptions", [])
            results = []
            
            for item in consumptions:
                quantity = item.get("quantity")
                if quantity is not None:
                    # Parse timestamp and ensure it is timezone aware (UTC)
                    ts_str = item["periodStart"].replace("Z", "+00:00")
                    results.append({
                        "timestamp": datetime.fromisoformat(ts_str),
                        "consumption": float(quantity)
                    })
            return results
