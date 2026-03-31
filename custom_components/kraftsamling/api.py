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
        
        :param username: This is the Customer ID from Home Assistant config
        :param password: This is the API Key from Home Assistant config
        """
        self.session = session
        self.username = str(username)
        self.password = password
        self.base_url = "https://io.dalakraft.se"
        self._token: Optional[str] = None

    @property
    def _default_headers(self) -> dict:
        """Standard headers required for all requests to Dalakraft IO."""
        return {
            "X-Customer-Id": self.username,
            "X-Api-Key": self.password,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def async_authenticate(self) -> bool:
        """
        Fetch a Bearer token from the /auth endpoint.
        Returns True if successful, otherwise False.
        """
        url = f"{self.base_url}/auth"
        payload = {
            "customerid": self.username,
            "apikey": self.password
        }

        try:
            _LOGGER.debug("Authenticating to %s", url)
            async with self.session.post(
                url, 
                json=payload, 
                headers=self._default_headers, 
                timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self._token = data.get("token")
                    if self._token:
                        return True
                    _LOGGER.error("Auth response missing 'token' field")
                else:
                    _LOGGER.error("Authentication failed with status %s", response.status)
                return False
        except Exception as err:
            _LOGGER.error("Error during authentication: %s", err)
            return False

    async def async_get_billingpoints(self) -> List[Any]:
        """
        Fetch billing points. 
        Returns a list of facilities or an empty list if it fails.
        """
        # Ensure we have a token
        if not self._token:
            if not await self.async_authenticate():
                return []

        url = f"{self.base_url}/Billingpoints"
        headers = self._default_headers.copy()
        headers["Authorization"] = f"Bearer {self._token}"

        try:
            async with self.session.get(url, headers=headers, timeout=10) as response:
                if response.status == 401:
                    _LOGGER.warning("Token expired, retrying once...")
                    self._token = None
                    # Recursive call once after clearing token
                    return await self.async_get_billingpoints()
                
                response.raise_for_status()
                return await response.json()
        except Exception as err:
            _LOGGER.error("Failed to fetch billing points: %s", err)
            return []

    async def async_get_volumes(self, billingpoints: List[str], start_date: str, end_date: str) -> List[Any]:
        """
        Fetch energy consumption volumes.
        Dates must be ISO strings without 'Z' (e.g. 2024-01-01T00:00:00).
        """
        if not self._token:
            if not await self.async_authenticate():
                return []

        url = f"{self.base_url}/Billingpoints/volumes"
        headers = self._default_headers.copy()
        headers["Authorization"] = f"Bearer {self._token}"
        
        payload = {
            "billingpoints": billingpoints,
            "from": start_date,
            "to": end_date
        }

        try:
            async with self.session.post(url, json=payload, headers=headers, timeout=15) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as err:
            _LOGGER.error("Failed to fetch volume data: %s", err)
            return []
