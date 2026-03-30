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

    def __init__(self, hass, api, start_date_str):
        """Initialize the coordinator."""
        super().__init__(
            hass, _LOGGER, name="Kraftsamling", update_interval=timedelta(hours=1)
        )
        self.api = api
        self.start_date = datetime.strptime(start_date_str, "%Y-%m-%d")

    async def _async_update_data(self):
        """Synchronize API data with the long-term statistics database."""
        facilities = await self.api.get_facilities()
        
        for facility in facilities:
            ext_id = facility.get('externalId')
            if not ext_id:
                continue

            # Unique identifier for the statistic in the database
            stat_id = f"{STATISTICS_ID_BASE}{ext_id}"
            
            # Fetch the most recent entry from the recorder to identify the sync gap
            last_stats = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 1, stat_id, True, {"sum"}
            )

            # Determine where to start fetching data
            if not last_stats or stat_id not in last_stats:
                fetch_cursor = self.start_date
                last_sum = 0.0
            else:
                # Start from the hour following the last saved data point
                fetch_cursor = datetime.fromtimestamp(last_stats[stat_id][0]["start"]) + timedelta(hours=1)
                last_sum = last_stats[stat_id][0]["sum"]

            # Guard: Only fetch if data is missing (more than 1 hour ago)
            now = datetime.now()
            current_sum = last_sum

            # Chunked processing to handle large historical imports without timeouts
            while fetch_cursor < now - timedelta(hours=1):
                chunk_end = min(fetch_cursor + timedelta(days=30), now)
                
                _LOGGER.info("Syncing %s: Fetching period %s to %s", ext_id, fetch_cursor, chunk_end)
                new_entries = await self.api.get_consumption_data(ext_id, fetch_cursor)
                
                if not new_entries:
                    _LOGGER.info("Reached end of available data for %s", ext_id)
                    break

                stats_to_import = []
                for entry in new_entries:
                    # Maintain a running total for the 'sum' attribute (Total Increasing)
                    current_sum += entry["consumption"]
                    stats_to_import.append(
                        StatisticData(
                            start=entry["timestamp"],
                            sum=current_sum,
                            state=current_sum
                        )
                    )

                # Define metadata for the statistics entity
                metadata = StatisticMetaData(
                    has_mean=False,
                    has_sum=True,
                    name=f"Kraftsamling {ext_id}",
                    source=DOMAIN,
                    statistic_id=stat_id,
                    unit_of_measurement="kWh",
                )
                
                # Directly inject data into the recorder
                async_import_statistics(self.hass, metadata, stats_to_import)
                
                # Advance the cursor to the end of the imported period
                fetch_cursor = new_entries[-1]["timestamp"] + timedelta(hours=1)

        return True
