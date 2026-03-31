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

### Manual Installation
1. Download the `custom_components/kraftsamling` folder.
2. Copy it into your Home Assistant `/config/custom_components/` directory.
3. Restart Home Assistant.

## Configuration

1. Go to **Settings** -> **Devices & Services**.
2. Click **Add Integration** and search for **Kraftsamling**.
3. Enter your credentials:
   * **CustomerId**: Your numerical customer ID from Dalakraft.
   * **API-Key**: Your unique GUID (found in the Dalakraft IO portal).
   * **Start Date**: The date you want to start importing data from (default is the first of the current month).
4. In the next step, select the **Facilities** (Billing points) you want to track.

## Finding your Credentials
To use this integration, you need access to the Dalakraft IO API. 
1. Log in to your account at [Dalakraft IO](https://io.dalakraft.se/).
2. You will find your **CustomerId** and **API-Key** under your profile or API settings.

## License
This project is licensed under the MIT License.
