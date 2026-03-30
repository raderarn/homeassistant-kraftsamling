[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
# Kraftsamling for Home Assistant

This integration fetches electricity consumption data from the [Kraftsamling API](https://api.kraftsamling.se/swagger/index.html) and injects it directly into the Home Assistant **Energy Dashboard**.

## Features
- **Historical Import:** Choose a start date (e.g., 2023-01-01) during setup to fetch all historical data.
- **Smart Polling:** If data for the previous day is missing, the integration retries every hour until values become available.
- **Native Energy Support:** Utilizes the Home Assistant statistics engine to provide accurate hour-by-hour consumption graphs.

## Installation

### Via HACS (Recommended)
1. Open HACS in Home Assistant.
2. Click the three dots in the top right corner and select **Custom repositories**.
3. Paste the URL to this GitHub repository and select **Integration** as the category.
4. Search for "Kraftsamling" and click **Download**.
5. Restart Home Assistant.

### Manual Installation
1. Download the `custom_components/kraftsamling` folder.
2. Copy the folder into your `config/custom_components/` directory.
3. Restart Home Assistant.

## Configuration
1. Navigate to **Settings** -> **Devices & Services**.
2. Click **Add Integration** and search for **Kraftsamling**.
3. Enter your **API Key** and the **Start Date** from which you want to begin fetching data.

## How to use the data in the Energy Dashboard
Since this integration uses `async_import_statistics`, it does not create standard sensor entities in your main overview.
1. Navigate to **Settings** -> **Dashboards** -> **Energy**.
2. Under **Electricity grid**, click **Add consumption**.
3. Search for `sensor.kraftsamling_anlaggning_YOURID` (where YOURID is your facility ID from Kraftsamling).
4. Save. It may take up to 2 hours before the first graphs start appearing.

## Troubleshooting
If you don't see any data, check the logs:
`Settings -> System -> Logs`

---
*Disclaimer: This integration is not affiliated with Kraftsamling. Use at your own risk.*
