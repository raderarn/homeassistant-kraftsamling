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
    """Coordinator to manage fetching data and importing statistics."""

    def __init__(self, hass, api, start_date_str):
        super().__init__(
            hass, 
            _LOGGER, 
            name="Kraftsamling Coordinator", 
            update_interval=timedelta(hours=1)
        )
        self.api = api
        self.start_date = datetime.strptime(start_date_str, "%Y-%m-%d")

    async def _async_update_data(self):
        """Fetch data from API and import into Home Assistant statistics."""
        facilities = await self.api.get_facilities()
        
        for facility in facilities:
            facility_id = facility['id']
            stat_id = f"{STATISTICS_ID_BASE}{facility_id}"
            
            # 1. Check for the last existing entry in the statistics database
            last_stats = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 1, stat_id, True, {"sum"}
            )

            if not last_stats or stat_id not in last_stats:
                fetch_from = self.start_date
                last_sum = 0.0
            else:
                fetch_from = datetime.fromtimestamp(last_stats[stat_id][0]["start"]) + timedelta(hours=1)
                last_sum = last_stats[stat_id][0]["sum"]

            # 2. Skip if data is already up to date (within the last 2 hours)
            if fetch_from > datetime.now() - timedelta(hours=2):
                _LOGGER.debug("Statistics for %s are already up to date", facility_id)
                continue

            # 3. Fetch new data from the API
            new_entries = await self.api.get_consumption_data(facility_id, fetch_from)
            if not new_entries:
                _LOGGER.info("No new data available for facility %s yet", facility_id)
                continue

            # 4. Convert consumption to accumulated sum for 'TOTAL_INCREASING' logic
            stats_to_import = []
            current_sum = last_sum
            for entry in new_entries:
                current_sum += entry["consumption"]
                stats_to_import.append(
                    StatisticData(
                        start=entry["timestamp"],
                        sum=current_sum,
                        state=current_sum
                    )
                )

            # 5. Build metadata and import into the recorder
            metadata = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                name=f"Kraftsamling {facility_id}",
                source=DOMAIN,
                statistic_id=stat_id,
                unit_of_measurement="kWh",
            )
            
            async_import_statistics(self.hass, metadata, stats_to_import)
            _LOGGER.info("Imported %s hourly values for %s", len(stats_to_import), facility_id)
            
        return True
