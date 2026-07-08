# Contarina Bin Detector for Home Assistant

Home Assistant add-on repository for detecting a Contarina waste bin in a camera feed.

The add-on reads an RTSP stream, checks a configured pixel area, detects a configured color range and publishes a Home Assistant `binary_sensor`. It is designed for the practical case where the bin should be considered exposed only on the correct collection day.

[![Open your Home Assistant instance and show the add add-on repository dialog with this repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FVanHelsing2048%2Fha-contarina-bin-detector)

## Add-on

- [Contarina Bin Detector](contarina-bin-detector)

## Features

- RTSP camera input.
- Pixel ROI configuration.
- HSV color detection with one or more color ranges.
- Day and time scheduling.
- Home Assistant `binary_sensor` state publishing through the Supervisor Core API.
- Useful attributes for tuning: color ratio, ROI, HSV ranges, schedule state and last scan time.

## Installation

1. Open Home Assistant.
2. Go to **Settings -> Add-ons -> Add-on Store**.
3. Open the menu in the top right and choose **Repositories**.
4. Add this repository URL:

```text
https://github.com/VanHelsing2048/ha-contarina-bin-detector
```

5. Install **Contarina Bin Detector**.

## Versioning

This repository uses semantic versioning. Add-on versions are defined in `contarina-bin-detector/config.yaml` and release notes are kept in:

- [CHANGELOG.md](CHANGELOG.md) for repository-level history.
- [contarina-bin-detector/CHANGELOG.md](contarina-bin-detector/CHANGELOG.md) for Home Assistant add-on release notes.

## Status

Initial release: `0.1.0`.

The add-on is marked as experimental until it has been tested against a real RTSP stream and a few lighting conditions.
