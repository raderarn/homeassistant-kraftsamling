"""Data update coordinator for Kraftsamling integration."""
import logging
from datetime import datetime, timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    get_last_statistics,
    StatisticMetaData,
    StatisticData,
)
from .const import DOMAIN, STATISTICS_ID_BASE

_LOGGER = logging.getLogger(__name__)

class KraftsamlingCoordinator(DataUpdateCoordinator):
    """Data update coordinator for Kraftsamling integration."""

    def __init__(self, hass, api, config_entry):
        """Initialize the coordinator."""
        super().__init__(
            hass, _LOGGER, name="Kraftsamling", update_interval=timedelta(hours=1)
        )
        self.api = api
        self.config_entry = config_entry
        # Use a safe default if start_date is missing
        start_date_str = config_entry.data.get("start_date", "2024-01-01")
        self.start_date = datetime.strptime(start_date_str, "%Y-%m-%d")

    async def _async_update_data(self):
        """Fetch consumption data from API and sync with long-term statistics."""
        selected_ids = self.config_entry.data.get("selected_facilities", [])
        
        if not selected_ids:
            _LOGGER.warning("No facilities selected for Kraftsamling.")
            return False

        for ext_id in selected_ids:
            try:
                stat_id = f"{STATISTICS_ID_BASE}{ext_id}"
                
                # Fetch last known statistic to determine where to resume
                last_stats = await get_instance(self.hass).async_add_executor_job(
                    get_last_statistics, self.hass, 1, stat_id, True, {"sum"}
                )

                if not last_stats or stat_id not in last_stats:
                    fetch_cursor = self.start_date
                    last_sum = 0.0
                else:
                    last_stat_time = last_stats[stat_id][0]["start"]
                    fetch_cursor = datetime.fromtimestamp(last_stat_time) + timedelta(hours=1)
                    last_sum = last_stats[stat_id][0]["sum"]

                now = datetime.now()
                current_sum = last_sum

                # Fetch data in 30-day chunks to prevent timeouts
                while fetch_cursor < now - timedelta(hours=1):
                    chunk_end = min(fetch_cursor + timedelta(days=30), now)
                    
                    start_str = fetch_cursor.strftime("%Y-%m-%d")
                    end_str = chunk_end.strftime("%Y-%m-%d")

                    _LOGGER.info("Fetching volumes for %s: %s to %s", ext_id, start_str, end_str)
                    
                    # API call returns a list of objects
                    response_data = await self.api.async_get_volumes([ext_id], start_str, end_str)
                    
                    # Target: response_data[0]["consumptions"]
                    new_entries = []
                    if isinstance(response_data, list) and len(response_data) > 0:
                        new_entries = response_data[0].get("consumptions", [])

                    if not new_entries:
                        _LOGGER.debug("No data found in this period for %s", ext_id)
                        break

                    stats_to_import = []
                    for entry in new_entries:
                        try:
                            # Map Dalakraft JSON keys
                            ts = datetime.fromisoformat(entry["periodStart"].replace("Z", ""))
                            val = float(entry["quantity"])
                            
                            if ts >= fetch_cursor:
                                current_sum += val
                                stats_to_import.append(
                                    StatisticData(
                                        start=ts,
                                        sum=current_sum,
                                        state=current_sum
                                    )
                                )
                        except (KeyError, ValueError, TypeError) as err:
                            _LOGGER.error("Skipping entry for %s: %s", ext_id, err)
                            continue

                    if stats_to_import:
                        # metadata['source'] MUST match DOMAIN exactly to avoid 'Invalid source'
                        metadata = StatisticMetaData(
                            has_mean=False,
                            has_sum=True,
                            name=f"Kraftsamling {ext_id}",
                            source=DOMAIN,
                            statistic_id=stat_id,
                            unit_of_measurement="kWh",
                        )
                        
                        _LOGGER.debug("Importing %s hours of statistics", len(stats_to_import))
                        async_import_statistics(self.hass, metadata, stats_to_import)
                        
                        # Move cursor to the hour after the last imported entry
                        fetch_cursor = stats_to_import[-1]["start"] + timedelta(hours=1)
                    else:
                        break

            except Exception as err:
                _LOGGER.error("Error updating facility %s: %s", ext_id, err)
                continue

        return True
