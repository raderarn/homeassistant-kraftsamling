import logging
import aiohttp
import async_timeout
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

class KraftsamlingAPI:
    def __init__(self, username, password, session: aiohttp.ClientSession):
        self.username = username
        self.password = password
        self._session = session
        self.base_url = "https://io.dalakraft.se"
        self._token = None

    async def _async_get_token(self):
        """Login and get the authToken from tokenUsers."""
        url = f"{self.base_url}/Auth"
        payload = {"User": self.username, "password": self.password}
        
        async with async_timeout.timeout(10):
            response = await self._session.post(url, json=payload)
            response.raise_for_status()
            res_data = await response.json()
            # Path based on your PowerShell: $Result.tokenUsers.authToken
            self._token = res_data.get("tokenUsers", {}).get("authToken")
            
        if not self._token:
            raise Exception("Could not find authToken in response")

    async def get_facilities(self) -> list:
        """Fetch billing points from .billingPoints."""
        if not self._token:
            await self._async_get_token()

        url = f"{self.base_url}/Billingpoints"
        headers = {"Authorization": self._token} # Skriptet skickar token rakt av

        async with async_timeout.timeout(10):
            response = await self._session.get(url, headers=headers)
            if response.status == 401: # Token expired
                await self._async_get_token()
                headers["Authorization"] = self._token
                response = await self._session.get(url, headers=headers)
            
            response.raise_for_status()
            data = await response.json()
            # Based on your PowerShell: $Billingpoints.billingPoints
            return data.get("billingPoints", [])

    async def get_consumption_data(self, external_id: str, start_dt: datetime) -> list:
        """Fetch volumes via POST request."""
        if not self._token:
            await self._async_get_token()

        # We fetch one day at a time or a range. 
        # For Energy Dashboard, we want 'hour' resolution if possible.
        # If 'hour' isn't supported, we use 'day'.
        url = f"{self.base_url}/Billingpoints/volumes"
        
        # End date is usually now or midnight
        end_dt = datetime.now()
        
        payload = {
            "billingpoints": [external_id],
            "resolution": "hour", # Skriptet hade "month", men Energy Dashboard vill ha "hour"
            "periodStart": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "periodEnd": end_dt.strftime("%Y-%m-%dT%H:%M:%S")
        }
        
        headers = {"Authorization": self._token}

        async with async_timeout.timeout(20):
            response = await self._session.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = await response.json()
            
            # The structure in PowerShell was $Values.consumptions.quantity
            # If resolution is 'hour', consumptions is likely a list.
            consumptions = data.get("consumptions", [])
            
            results = []
            for item in consumptions:
                if item.get("quantity") is not None:
                    results.append({
                        "timestamp": datetime.fromisoformat(item["periodStart"].replace("Z", "+00:00")),
                        "consumption": float(item["quantity"])
                    })
            return results
