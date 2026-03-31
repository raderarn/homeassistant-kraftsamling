"""Dalakraft IO API Client."""
import logging
import aiohttp
from typing import Any, Optional, List

_LOGGER = logging.getLogger(__name__)

class KraftsamlingAPI:
    """Class to communicate with the Dalakraft IO API."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str):
        """
        Initialize the API client.
        
        IMPORTANT: The order of arguments must match the call in config_flow.py.
        """
        self.session = session
        self.username = str(username)
        self.password = password
        self.base_url = "https://io.dalakraft.se"
        self._token: Optional[str] = None

    @property
    def _default_headers(self) -> dict:
        """Standard headers matching the verified PowerShell script requirements."""
        return {
            "accept": "text/plain",
            "Content-Type": "application/json",
            "User-Agent": "HomeAssistant-Kraftsamling/1.0"
        }

    async def async_authenticate(self) -> bool:
        """
        Fetch authToken using the User/password structure.
        Based on the successful PowerShell authentication flow.
        """
        url = f"{self.base_url}/Auth"
        payload = {
            "User": self.username,
            "password": self.password
        }

        try:
            _LOGGER.debug("Attempting authentication for user: %s", self.username)
            # self.session is now correctly received as an aiohttp.ClientSession object
            async with self.session.post(
                url, 
                json=payload, 
                headers=self._default_headers, 
                timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # Navigating the response path: $Result.tokenUsers.authToken
                    token_users = data.get("tokenUsers", {})
                    self._token = token_users.get("authToken")
                    
                    if self._token:
                        _LOGGER.debug("Authentication successful, token received.")
                        return True
                    
                    _LOGGER.error("Auth response succeeded but 'tokenUsers.authToken' was missing.")
                else:
                    _LOGGER.error("Authentication failed with status code: %s", response.status)
                return False
        except Exception as err:
            _LOGGER.error("Unexpected error during authentication: %s", err)
            return False

    async def async_get_billingpoints(self) -> List[Any]:
        """Fetch billing points (facilities) using the retrieved authToken."""
        if not self._token:
            if not await self.async_authenticate():
                return []

        url = f"{self.base_url}/Billingpoints"
        headers = self._default_headers.copy()
        # Authorization header uses the raw token without 'Bearer' prefix
        headers["Authorization"] = self._token

        try:
            async with self.session.get(url, headers=headers, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                
                # Extracting billing points from the response object
                if isinstance(data, dict) and "billingPoints" in data:
                    return data["billingPoints"]
                return data if isinstance(data, list) else []
        except Exception as err:
            _LOGGER.error("Failed to fetch billing points: %s", err)
            return []

    async def async_get_volumes(self, billingpoints: List[str], start_date: str, end_date: str) -> List[Any]:
        """
        Fetch energy consumption volumes.
        Dates should be provided in yyyy-MM-dd format.
        """
        if not self._token:
            if not await self.async_authenticate():
                return []

        url = f"{self.base_url}/Billingpoints/volumes"
        headers = self._default_headers.copy()
        headers["Authorization"] = self._token
        
        # Payload matches the ordered dictionary from the PowerShell script
        payload = {
            "billingpoints": billingpoints,
            "resolution": "hour",
            "periodStart": start_date,
            "periodEnd": end_date
        }

        try:
            async with self.session.post(url, json=payload, headers=headers, timeout=15) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as err:
            _LOGGER.error("Failed to fetch volume data: %s", err)
            return []
