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
        """Authenticate and retrieve a bearer token from the tokenUsers list."""
        url = f"{self.base_url}/Auth"
        payload = {"User": self.username, "password": self.password}
        
        _LOGGER.debug("Authenticating against Dalakraft IO for user: %s", self.username)
        
        async with async_timeout.timeout(10):
            response = await self._session.post(url, json=payload)
            response.raise_for_status()
            res_data = await response.json()
            
            # Dalakraft IO returns tokenUsers as a list. We need the first element.
            token_list = res_data.get("tokenUsers", [])
            if isinstance(token_list, list) and len(token_list) > 0:
                self._token = token_list[0].get("authToken")
            else:
                _LOGGER.error("Authentication failed: tokenUsers list is empty or invalid")
                raise Exception("No valid token received")
            
        if not self._token:
            _LOGGER.error("Authentication failed: authToken not found in response")
            raise Exception("Access denied")

    async def get_facilities(self) -> list:
        """Fetch all billing points associated with the account."""
        if not self._token:
            await self._async_get_token()

        url = f"{self.base_url}/Billingpoints"
        
        try:
            return await self._make_request("GET", url)
        except Exception as err:
            _LOGGER.error("Failed to fetch billing points: %s", err)
            return []

    async def get_consumption_data(self, external_id: str, start_dt: datetime) -> list:
            """Fetch hourly consumption volumes via POST request."""
            url = f"{self.base_url}/Billingpoints/volumes"
            end_dt = datetime.now()
            
            payload = {
                "billingpoints": [external_id],
                "resolution": "hour",
                "periodStart": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "periodEnd": end_dt.strftime("%Y-%m-%dT%H:%M:%S")
            }
    
            try:
                # data will now be the raw list returned from the API
                data = await self._make_request("POST", url, json_payload=payload)
                
                # The API returns a list of consumption objects directly
                # If it's already a list, we use it. If not, we try to get 'consumptions'
                consumptions = data if isinstance(data, list) else data.get("consumptions", [])
                
                results = []
                for item in consumptions:
                    quantity = item.get("quantity")
                    if quantity is not None:
                        # Parse timestamp and ensure it is timezone aware
                        ts_str = item["periodStart"].replace("Z", "+00:00")
                        results.append({
                            "timestamp": datetime.fromisoformat(ts_str),
                            "consumption": float(quantity)
                        })
                
                _LOGGER.debug("Fetched %s consumption records for %s", len(results), external_id)
                return results
    
            except Exception as err:
                _LOGGER.warning("Could not fetch volumes for %s: %s", external_id, err)
                return []
            
    async def _make_request(self, method, url, json_payload=None):
        """Make an async HTTP request with automatic token retry on 401."""
        if not self._token:
            await self._async_get_token()

        for attempt in range(2):  # Try twice: once with current token, once with fresh
            headers = {
                "Authorization": self._token,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            try:
                async with async_timeout.timeout(20):
                    if method == "GET":
                        response = await self._session.get(url, headers=headers)
                    else:
                        response = await self._session.post(url, json=json_payload, headers=headers)

                    # If token is expired (401), fetch a new one and retry once
                    if response.status == 401 and attempt == 0:
                        _LOGGER.info("Token expired (401), refreshing and retrying...")
                        await self._async_get_token()
                        continue

                    response.raise_for_status()
                    
                    # For Billingpoints, the data is in .billingPoints
                    # For Volumes, the data is the whole response
                    res_json = await response.json()
                    if "billingPoints" in res_json:
                        return res_json.get("billingPoints", [])
                    return res_json

            except aiohttp.ClientResponseError as err:
                if err.status == 401 and attempt == 0:
                    await self._async_get_token()
                    continue
                raise
