"""Data update coordinator for Kraftsamling."""
import logging
from datetime import datetime, timedelta, timezone
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
    """Coordinator to fetch and import historical consumption data."""

    def __init__(self, hass, api, config_entry):
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(hours=1))
        self.api = api
        self.config_entry = config_entry
        
        # Vi lagrar både totalsumman (för kalkylen) och senaste timmen (för display)
        self.last_sum = 0.0
        self.last_hour_consumption = 0.0
        
        start_str = config_entry.data.get("start_date", "2024-01-01")
        self.start_date = datetime.strptime(start_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    async def _async_update_data(self):
        """Fetch and sync statistics with the Home Assistant database."""
        selected_ids = self.config_entry.data.get("selected_facilities", [])
        if not selected_ids:
            return False

        for ext_id in selected_ids:
            try:
                stat_id = f"{STATISTICS_ID_BASE}{ext_id}".lower().strip()

                last_stats = await get_instance(self.hass).async_add_executor_job(
                    get_last_statistics, self.hass, 1, stat_id, True, {"sum"}
                )

                if not last_stats or stat_id not in last_stats:
                    fetch_cursor = self.start_date
                    self.last_sum = 0.0
                else:
                    last_stat_time = last_stats[stat_id][0]["start"]
                    fetch_cursor = datetime.fromtimestamp(last_stat_time, tz=timezone.utc) + timedelta(hours=1)
                    self.last_sum = last_stats[stat_id][0]["sum"]

                now = datetime.now(timezone.utc)
                current_sum = self.last_sum

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
                            raw_ts = entry["periodStart"]
                            if raw_ts.endswith("Z"):
                                ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                            elif "+" not in raw_ts:
                                ts = datetime.fromisoformat(raw_ts).replace(tzinfo=timezone.utc)
                            else:
                                ts = datetime.fromisoformat(raw_ts)

                            val = float(entry["quantity"])
                            
                            if ts >= fetch_cursor:
                                current_sum += val
                                stats_to_import.append(
                                    StatisticData(start=ts, sum=current_sum, state=current_sum)
                                )
                                # Spara det senaste värdet för att visa i sensorn
                                self.last_hour_consumption = val
                                
                        except Exception as e:
                            _LOGGER.warning("Failed to parse entry: %s", e)
                            continue

                    if stats_to_import:
                        metadata = StatisticMetaData(
                            has_mean=False,
                            has_sum=True,
                            name=f"Kraftsamling {ext_id}",
                            source="recorder",
                            statistic_id=stat_id,
                            unit_of_measurement="kWh",
                            mean_type=None,
                        )
                        async_import_statistics(self.hass, metadata, stats_to_import)
                        self.last_sum = current_sum
                        fetch_cursor = stats_to_import[-1]["start"] + timedelta(hours=1)
                    else:
                        break

            except Exception as err:
                _LOGGER.error("Update failed for %s: %s", ext_id, err)

        # Vi returnerar senaste timmens förbrukning istället för totalsumman
        return self.last_hour_consumption
