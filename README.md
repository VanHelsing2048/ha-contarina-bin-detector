# Contarina Bin Detector for Home Assistant

Home Assistant add-on repository for detecting a Contarina waste bin in a camera feed.

The add-on reads an RTSP stream, checks a configured pixel area, detects whether a gray, yellow or blue bin is visible and publishes a Home Assistant `sensor`. It is designed for the practical case where the bin should be considered exposed only on the correct collection day.

[![Open your Home Assistant instance and show the add add-on repository dialog with this repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FVanHelsing2048%2Fha-contarina-bin-detector)

## Add-on

- [Contarina Bin Detector](contarina-bin-detector)

## Features

- RTSP camera input.
- Periodic fresh RTSP snapshot capture, defaulting to one scan every 5 minutes.
- Home Assistant add-on Configuration schema for stable settings.
- Ingress Web UI for snapshot, ROI selection, debug overlay and notification testing.
- HSV color detection for gray, yellow and blue bins.
- Contarina color presets derived from the provided CAR, SEC and VPL reference images.
- Expected collection sensor mapping for `Carta`, `VPL`, `Umido` and `Secco`.
- Low-light detection to avoid false negatives when the camera cannot see the bin.
- Mobile app notifications through a configured `notify.mobile_app_*` service.
- Mobile notification test action from the Web UI.
- Debug snapshot with ROI overlay, detected state, color ratios and image quality metrics.
- Ingress Web UI with RTSP snapshot and visual rectangle selection.
- Day and time scheduling.
- Home Assistant `sensor` state publishing through the Supervisor Core API.
- Prebuilt multi-architecture Docker images published to GitHub Container Registry.
- Useful attributes for tuning: color ratios, ROI, HSV ranges, schedule state and last scan time.

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

Current release: `0.11.14`.

The add-on is marked as experimental until it has been tested against a real RTSP stream and a few lighting conditions.
