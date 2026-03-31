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
        
        :param session: aiohttp.ClientSession provided by Home Assistant
        :param username: Customer ID / User
        :param password: API Key / Password
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
        Fetch authToken by navigating the exact JSON structure:
        data['tokenUsers'][0]['authToken']
        """
        url = f"{self.base_url}/Auth"
        payload = {
            "User": self.username,
            "password": self.password
        }

        try:
            _LOGGER.debug("Attempting authentication for user: %s", self.username)
            async with self.session.post(
                url, 
                json=payload, 
                headers=self._default_headers, 
                timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Structure: {"tokenUsers": [{"name": "", "authToken": "..."}]}
                    token_list = data.get("tokenUsers", [])
                    
                    if isinstance(token_list, list) and len(token_list) > 0:
                        self._token = token_list[0].get("authToken")
                    
                    if self._token:
                        _LOGGER.debug("Authentication successful, authToken received.")
                        return True
                    
                    _LOGGER.error("Auth response structure mismatch or missing token. Data: %s", data)
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
        # Authorization header uses the raw token directly (no Bearer prefix)
        headers["Authorization"] = self._token

        try:
            async with self.session.get(url, headers=headers, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                
                # Extract billing points based on your PowerShell script structure
                if isinstance(data, dict) and "billingPoints" in data:
                    return data["billingPoints"]
                return data if isinstance(data, list) else []
        except Exception as err:
            _LOGGER.error("Failed to fetch billing points: %s", err)
            return []

    async def async_get_volumes(self, billingpoints: List[str], start_date: str, end_date: str) -> List[Any]:
        """
        Fetch energy consumption volumes.
        Dates are provided in yyyy-MM-dd format.
        """
        if not self._token:
            if not await self.async_authenticate():
                return []

        url = f"{self.base_url}/Billingpoints/volumes"
        headers = self._default_headers.copy()
        headers["Authorization"] = self._token
        
        # Matches the payload requirements for Dalakraft IO Volumes
        payload = {
            "billingpoints": billingpoints,
            "resolution": "hour",
            "periodStart": start_date,
            "periodEnd": end_date
        }

        try:
            _LOGGER.debug("Requesting volumes for %s from %s to %s", billingpoints, start_date, end_date)
            async with self.session.post(url, json=payload, headers=headers, timeout=15) as response:
                response.raise_for_status()
                data = await response.json()
                
                # Flexibility to handle if the data is wrapped in a key (e.g., 'values' or 'out')
                if isinstance(data, dict):
                    actual_list = data.get("values") or data.get("billingPoints") or data.get("out")
                    if actual_list is not None:
                        return actual_list
                    _LOGGER.warning("API returned a dictionary but no known data key was found: %s", data.keys())
                    return []
                
                return data if isinstance(data, list) else []
        except Exception as err:
            _LOGGER.error("Failed to fetch volume data: %s", err)
            return []
