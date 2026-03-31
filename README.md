# Kraftsamling for Home Assistant

<p align="center">
  <img src="https://raw.githubusercontent.com/raderarn/homeassistant-kraftsamling/main/logo.png" width="200" alt="Dalakraft Logo">
</p>

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![Version](https://img.shields.io/github/v/release/raderarn/homeassistant-kraftsamling)

An integration for Home Assistant that fetches electricity consumption data from **Dalakraft IO**. It imports data directly into Home Assistant's long-term statistics, making it perfect for use with the **Energy Dashboard**.

## Features
* **Long-term Statistics**: Data is stored efficiently in the Home Assistant database.
* **Energy Dashboard Integration**: Supports the native Energy Dashboard.
* **Multi-facility Support**: Select which billing points (facilities) to track during setup.
* **Automatic History Sync**: Automatically fetches historical data from a chosen start date.

## Installation

### Via HACS (Recommended)
1. Open **HACS** in your Home Assistant instance.
2. Click on the three dots in the top right corner and select **Custom repositories**.
3. Add `https://github.com/raderarn/homeassistant-kraftsamling` as an **Integration**.
4. Click **Install**.
5. Restart Home Assistant.

## Configuration

1. Go to **Settings** -> **Devices & Services**.
2. Click **Add Integration** and search for **Kraftsamling**.
3. Enter your credentials:
   * **CustomerId**: Your numerical customer ID from Dalakraft.
   * **API-Key**: Your unique GUID (found in the Dalakraft IO portal).
   * **Start Date**: The date you want to start importing data from (default is the first of the current month).
4. In the next step, select the **Facilities** (Billing points) you want to track.

## How to use the data

Since this integration imports **Long-term Statistics** rather than creating real-time sensors, you will find the data in the following places:

### 1. Energy Dashboard (Recommended)
This is the best way to visualize your electricity consumption.
1. Go to **Settings** -> **Dashboards** -> **Energy**.
2. Click **Add consumption** under the *Electricity grid* section.
3. Search for your facility, it will appear as `Kraftsamling [Installation Address] ([ID])`.
4. **Note:** It can take up to **2 hours** after the first sync before the statistics are processed by Home Assistant and become visible in the list.

### 2. Developer Tools
To verify that data has been imported correctly:
1. Go to **Developer Tools** -> **Statistics**.
2. Search for `kraftsamling`.
3. You should see your facilities listed there. If there is a button that says **Fix issue**, click it to see if there are any unit mismatches (though the integration handles this automatically).

### 3. Statistics Graph Card
You can also add a manual graph to any dashboard:
1. Add a new **Statistics Graph** card to your Lovelace UI.
2. Select your Kraftsamling entities.
3. Change the period to "Day", "Week", or "Month" to see your historical Dalakraft data.

## Finding your Credentials
To use this integration, you need access to the Dalakraft IO API. 
You need to contact customer services to retreive your key. 

## License
This project is licensed under the MIT License.
