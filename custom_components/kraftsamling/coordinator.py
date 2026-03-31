"""Data update coordinator for Kraftsamling."""
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
    """Coordinator to fetch and import data."""

    def __init__(self, hass, api, config_entry):
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(hours=1))
        self.api = api
        self.config_entry = config_entry
        start_str = config_entry.data.get("start_date", "2024-01-01")
        self.start_date = datetime.strptime(start_str, "%Y-%m-%d")

    async def _async_update_data(self):
        """Fetch and sync statistics."""
        selected_ids = self.config_entry.data.get("selected_facilities", [])
        if not selected_ids:
            return False

        for ext_id in selected_ids:
            try:
                stat_id = f"{STATISTICS_ID_BASE}{ext_id}"
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

                while fetch_cursor < now - timedelta(hours=1):
                    chunk_end = min(fetch_cursor + timedelta(days=30), now)
                    response_data = await self.api.async_get_volumes(
                        [ext_id], fetch_cursor.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")
                    )
                    
                    new_entries = []
                    if isinstance(response_data, list) and len(response_data) > 0:
                        new_entries = response_data[0].get("consumptions", [])

                    if not new_entries:
                        break

                    stats_to_import = []
                    for entry in new_entries:
                        try:
                            ts = datetime.fromisoformat(entry["periodStart"].replace("Z", ""))
                            val = float(entry["quantity"])
                            if ts >= fetch_cursor:
                                current_sum += val
                                stats_to_import.append(
                                    StatisticData(start=ts, sum=current_sum, state=current_sum)
                                )
                        except:
                            continue

                    if stats_to_import:
                        metadata = StatisticMetaData(
                            has_mean=False,
                            has_sum=True,
                            name=f"Kraftsamling {ext_id}",
                            source=DOMAIN, # MUST be "kraftsamling"
                            statistic_id=stat_id,
                            unit_of_measurement="kWh",
                        )
                        async_import_statistics(self.hass, metadata, stats_to_import)
                        fetch_cursor = stats_to_import[-1]["start"] + timedelta(hours=1)
                    else:
                        break
            except Exception as err:
                _LOGGER.error("Update failed for %s: %s", ext_id, err)
        return True
