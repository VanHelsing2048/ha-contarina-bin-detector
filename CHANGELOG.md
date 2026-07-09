# Changelog

All notable changes to this repository are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses semantic versioning.

## [0.9.2] - 2026-07-09

### Fixed

- Added `init: false` so Home Assistant Supervisor does not wrap the s6-based image with an extra Docker init process.

## [0.9.1] - 2026-07-09

### Fixed

- Fixed add-on startup by moving the detector process into the standard s6 service directory and leaving the Home Assistant base image init process as PID 1.

## [0.9.0] - 2026-07-08

### Added

- Added a Web UI test action for the configured smartphone notify service.
- Added a debug snapshot action with ROI overlay, current detection result, expected collection, color ratios and image-quality metrics.

## [0.8.0] - 2026-07-08

### Changed

- Updated default HSV color ranges using the provided CAR, SEC and VPL reference images.
- Added a Web UI action to reapply the Contarina color presets to existing settings.

## [0.7.0] - 2026-07-08

### Added

- Added mobile app notification settings in the Web UI.
- Added reminder notifications when the expected bin is not detected.
- Added automatic notification clearing when the expected bin is detected.
- Added unreliable-verification notifications for dark, low-contrast or blurry images.
- Added add-on icon.

### Fixed

- Changed container startup to use `run.sh`, matching the Home Assistant base image startup pattern.

## [0.6.0] - 2026-07-08

### Changed

- Changed detection to capture a fresh RTSP snapshot per scan instead of keeping the stream open continuously.
- Set the default scan interval to 300 seconds.
- Set the default stable frame count to 1 for five-minute scans.
- The Web UI refresh action now captures a fresh frame on demand.

## [0.5.0] - 2026-07-08

### Added

- Added graphical configuration for an external Home Assistant collection sensor.
- Added mapping from `Carta`, `VPL`, `Umido` and `Secco` to expected bin colors.
- Added expected collection attributes: `expected_collection`, `expected_color`, `expected_match` and `verification_active`.
- Added ROI brightness measurement and `non_verificabile_buio` state when the image is too dark to trust.

## [0.4.0] - 2026-07-08

### Changed

- Moved all user configuration from Home Assistant add-on YAML options to the Ingress Web UI.
- The add-on now starts without manual YAML configuration and waits for the RTSP URL to be saved in the UI.
- Configuration is persisted in `/data/settings.json`.
- The Web UI now edits RTSP URL, sensor entity, name, timezone, schedule, scan settings, HSV thresholds and ROI.

## [0.3.0] - 2026-07-08

### Added

- Added Home Assistant Ingress panel for visual ROI selection.
- Added RTSP snapshot preview in the add-on UI.
- Added rectangle drawing and persistent ROI saving to `/data/roi.json`.
- The detector now reloads the saved ROI while running.

## [0.2.0] - 2026-07-08

### Changed

- Changed the Home Assistant entity from a binary sensor to a text sensor.
- The sensor state is now `grigio`, `giallo`, `blu` or `nessun_bidone`.
- Added separate HSV bounds for gray, yellow and blue bin detection.
- Added per-color ratio attributes to simplify tuning.

## [0.1.0] - 2026-07-08

### Added

- Initial Home Assistant add-on repository.
- Added Contarina Bin Detector add-on.
- Added RTSP frame capture with OpenCV.
- Added pixel ROI color detection using HSV lower and upper bounds.
- Added collection day and time-window scheduling.
- Added Home Assistant `binary_sensor` publishing through the Supervisor Core API.
- Added user documentation for installation, configuration, ROI and HSV tuning.
