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

# Fast tidszon för Normaltid (UTC+1) året om
CET_FIXED = timezone(timedelta(hours=1))

class KraftsamlingCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch and import historical consumption data."""

    def __init__(self, hass, api, config_entry):
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(hours=1))
        self.api = api
        self.config_entry = config_entry
        self.last_hour_consumption = 0.0
        self.last_sum = 0.0
        
        # Hämta startdatumet som användaren valt i config_flow.
        # Om inget finns (vilket inte ska hända med din setup), kör vi 2024-01-01.
        start_str = config_entry.data.get("start_date", "2024-01-01")
        
        try:
            # Tolka användarens valda datum som midnatt i fast UTC+1 (Normaltid)
            self.start_date = datetime.strptime(start_str, "%Y-%m-%d").replace(tzinfo=CET_FIXED)
            _LOGGER.debug("Coordinator initialized with start date: %s", self.start_date)
        except ValueError:
            _LOGGER.error("Invalid start_date format: %s. Using 2024-01-01", start_str)
            self.start_date = datetime(2024, 1, 1, tzinfo=CET_FIXED)

    async def _async_update_data(self):
        """Fetch and sync statistics."""
        selected_ids = self.config_entry.data.get("selected_facilities", [])
        if not selected_ids:
            return False

        for ext_id in selected_ids:
            try:
                stat_id = f"{STATISTICS_ID_BASE}{ext_id}".lower().strip()

                # Kolla vad som redan finns i Home Assistants databas
                last_stats = await get_instance(self.hass).async_add_executor_job(
                    get_last_statistics, self.hass, 1, stat_id, True, {"sum"}
                )

                if not last_stats or stat_id not in last_stats:
                    # Om inget finns, börja från användarens valda startdatum
                    fetch_cursor = self.start_date
                    self.last_sum = 0.0
                else:
                    # Annars, fortsätt från där vi slutade sist
                    last_stat_time = last_stats[stat_id][0]["start"]
                    fetch_cursor = datetime.fromtimestamp(last_stat_time, tz=timezone.utc).astimezone(CET_FIXED) + timedelta(hours=1)
                    self.last_sum = last_stats[stat_id][0]["sum"]

                now = datetime.now(timezone.utc)
                current_sum = self.last_sum

                # Hämta data fram till nuvarande tidpunkt
                while fetch_cursor < now - timedelta(hours=1):
                    chunk_end = min(fetch_cursor + timedelta(days=30), now.astimezone(CET_FIXED))
                    
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
                            # Tvätta bort Z/offset och tolka som fast UTC+1 (Normaltid)
                            clean_ts = raw_ts.split('+')[0].split('Z')[0]
                            local_ts = datetime.fromisoformat(clean_ts).replace(tzinfo=CET_FIXED)
                            
                            # Konvertera till UTC för Home Assistant (drar bort 1 timme)
                            ts_utc = local_ts.astimezone(timezone.utc)
                            val = float(entry["quantity"])
                            
                            if local_ts >= fetch_cursor:
                                current_sum += val
                                stats_to_import.append(
                                    StatisticData(start=ts_utc, sum=current_sum, state=current_sum)
                                )
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
                            mean_type=0, 
                            unit_class="energy",
                        )
                        async_import_statistics(self.hass, metadata, stats_to_import)
                        self.last_sum = current_sum
                        fetch_cursor = local_ts + timedelta(hours=1)
                    else:
                        break

            except Exception as err:
                _LOGGER.error("Update failed for %s: %s", ext_id, err)

        return self.last_hour_consumption
