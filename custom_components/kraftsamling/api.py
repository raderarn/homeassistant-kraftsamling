"""Dalakraft IO API Client."""
import logging
import aiohttp
from typing import Any, Optional, List

_LOGGER = logging.getLogger(__name__)

class KraftsamlingAPI:
    """Class to communicate with the Dalakraft IO API."""

    # ORDNINGEN HÄR ÄR KRITISK: session först, sen username, sen password
    def __init__(self, session: aiohttp.ClientSession, username: str, password: str):
        """Initialize the API client."""
        self.session = session
        self.username = str(username)
        self.password = password
        self.base_url = "https://io.dalakraft.se"
        self._token: Optional[str] = None

    @property
    def _default_headers(self) -> dict:
        """Standard headers matching the working PowerShell script."""
        return {
            "accept": "text/plain",
            "Content-Type": "application/json",
            "User-Agent": "HomeAssistant-Kraftsamling/1.0"
        }

    async def async_authenticate(self) -> bool:
        """Fetch authToken using User/password structure."""
        url = f"{self.base_url}/Auth"
        payload = {
            "User": self.username,
            "password": self.password
        }

        try:
            # Nu kommer self.session vara det riktiga aiohttp-objektet
            async with self.session.post(
                url, 
                json=payload, 
                headers=self._default_headers, 
                timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # Path from your PowerShell script: $Result.tokenUsers.authToken
                    token_users = data.get("tokenUsers", {})
                    self._token = token_users.get("authToken")
                    
                    if self._token:
                        return True
                _LOGGER.error("Authentication failed with status %s", response.status)
                return False
        except Exception as err:
            _LOGGER.error("Error during authentication: %s", err)
            return False

    async def async_get_billingpoints(self) -> List[Any]:
        """Fetch billing points using the authToken."""
        if not self._token:
            if not await self.async_authenticate():
                return []

        url = f"{self.base_url}/Billingpoints"
        headers = self._default_headers.copy()
        headers["Authorization"] = self._token

        try:
            async with self.session.get(url, headers=headers, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                
                # Based on PS script, return the list of points
                if isinstance(data, dict) and "billingPoints" in data:
                    return data["billingPoints"]
                return data if isinstance(data, list) else []
        except Exception as err:
            _LOGGER.error("Failed to fetch billing points: %s", err)
            return []
