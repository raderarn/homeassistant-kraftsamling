"""Dalakraft IO API Client."""
import logging
import asyncio
import aiohttp
from typing import Any, Optional

_LOGGER = logging.getLogger(__name__)

class KraftsamlingAPI:
    """Class to communicate with the Dalakraft IO API."""

    def __init__(self, session: aiohttp.ClientSession, customer_id: str, api_key: str):
        """Initialize the API client."""
        self.session = session
        self.customer_id = str(customer_id)
        self.api_key = api_key
        self.base_url = "https://io.dalakraft.se"
        self._token: Optional[str] = None

    @property
    def _default_headers(self) -> dict:
        """Standard headers required for all requests."""
        return {
            "X-Customer-Id": self.customer_id,
            "X-Api-Key": self.api_key,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def async_authenticate(self) -> bool:
        """Fetch a Bearer token from the /auth endpoint."""
        url = f"{self.base_url}/auth"
        
        # Payload according to Dalakraft IO standards
        payload = {
            "customerid": self.customer_id,
            "apikey": self.api_key
        }

        try:
            _LOGGER.debug("Attempting authentication against %s", url)
            async with self.session.post(
                url, 
                json=payload, 
                headers=self._default_headers, 
                timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # Extract token from the JSON response
                    self._token = data.get("token")
                    
                    if self._token:
                        _LOGGER.debug("Authentication successful, token received.")
                        return True
                    
                    _LOGGER.error("Auth response missing 'token' field: %s", data)
                    return False
                
                _LOGGER.error("Authentication failed with status %s", response.status)
                return False

        except Exception as e:
            _LOGGER.error("Unexpected error during authentication: %s", e)
            return False

    async def _get_authenticated_headers(self) -> dict:
        """Get headers including the Authorization token."""
        if not self._token:
            await self.async_authenticate()
            
        headers = self._default_headers.copy()
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def async_get_billingpoints(self) -> list:
        """Fetch the list of billing points (facilities)."""
        url = f"{self.base_url}/Billingpoints"
        headers = await self._get_authenticated_headers()

        try:
            async with self.session.get(url, headers=headers, timeout=10) as response:
                if response.status == 401:
                    _LOGGER.warning("Token invalid (401), attempting to refresh...")
                    self._token = None # Clear expired token
                    headers = await self._get_authenticated_headers()
                    # Retry once with a new token
                    async with self.session.get(url, headers=headers) as retry_resp:
                        retry_resp.raise_for_status()
                        return await retry_resp.json()

                response.raise_for_status()
                return await response.json()

        except Exception as e:
            _LOGGER.error("Error fetching billingpoints: %s", e)
            return []

    async def async_get_volumes(self, billingpoints: list, start_date: str, end_date: str) -> list:
        """Fetch consumption data (volumes)."""
        url = f"{self.base_url}/Billingpoints/volumes"
        headers = await self._get_authenticated_headers()
        
        # Payload format: billingpoints as a list of strings
        # Dates should be ISO strings without 'Z', e.g., 2024-01-01T00:00:00
        payload = {
            "billingpoints": billingpoints,
            "from": start_date,
            "to": end_date
        }

        try:
            async with self.session.post(url, json=payload, headers=headers, timeout=15) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            _LOGGER.error("Error fetching volume data: %s", e)
            return []
