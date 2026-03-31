"""Dalakraft IO API Client."""
import logging
import aiohttp
from typing import Any, Optional, List

_LOGGER = logging.getLogger(__name__)

class KraftsamlingAPI:
    """Class to communicate with the Dalakraft IO API."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str):
        """Initialize the API client."""
        self.session = session
        self.username = str(username)
        self.password = password
        self.base_url = "https://io.dalakraft.se"
        self._token: Optional[str] = None

    @property
    def _default_headers(self) -> dict:
        """Standard headers matching the PowerShell script."""
        return {
            "accept": "text/plain",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    async def async_authenticate(self) -> bool:
        """Fetch authToken using the User/password structure."""
        url = f"{self.base_url}/Auth"
        # PowerShell uses @{"User"= $User;"password"= $password}
        payload = {
            "User": self.username,
            "password": self.password
        }

        try:
            async with self.session.post(
                url, 
                json=payload, 
                headers=self._default_headers, 
                timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # PowerShell path: $Result.tokenUsers.authToken
                    token_users = data.get("tokenUsers", {})
                    self._token = token_users.get("authToken")
                    
                    if self._token:
                        _LOGGER.debug("Successfully authenticated and retrieved authToken")
                        return True
                    _LOGGER.error("Auth response missing tokenUsers.authToken")
                else:
                    _LOGGER.error("Auth failed with status %s", response.status)
                return False
        except Exception as err:
            _LOGGER.error("Error during authentication: %s", err)
            return False

    async def async_get_billingpoints(self) -> List[Any]:
        """Fetch billing points using the raw authToken."""
        if not self._token:
            if not await self.async_authenticate():
                return []

        url = f"{self.base_url}/Billingpoints"
        headers = self._default_headers.copy()
        # PowerShell: $header.Add("Authorization" , $authToken) -> No "Bearer "
        headers["Authorization"] = self._token

        try:
            async with self.session.get(url, headers=headers, timeout=10) as response:
                if response.status == 401:
                    self._token = None
                    if await self.async_authenticate():
                        headers["Authorization"] = self._token
                        async with self.session.get(url, headers=headers) as retry_resp:
                            return await retry_resp.json()
                
                response.raise_for_status()
                return await response.json()
        except Exception as err:
            _LOGGER.error("Failed to fetch billing points: %s", err)
            return []

    async def async_get_volumes(self, billingpoints: List[str], start_date: str, end_date: str) -> List[Any]:
        """Fetch volumes using periodStart/periodEnd keys."""
        if not self._token:
            await self.async_authenticate()

        url = f"{self.base_url}/Billingpoints/volumes"
        headers = self._default_headers.copy()
        headers["Authorization"] = self._token
        
        # PowerShell: "periodStart", "periodEnd" and "resolution"
        payload = {
            "billingpoints": billingpoints,
            "resolution": "hour",
            "periodStart": start_date, # Format: yyyy-MM-dd
            "periodEnd": end_date
        }

        try:
            async with self.session.post(url, json=payload, headers=headers, timeout=15) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as err:
            _LOGGER.error("Failed to fetch volume data: %s", err)
            return []
