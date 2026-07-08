# Changelog

Release notes for the Home Assistant add-on preview.

## [0.6.0] - 2026-07-08

### Changed

- Detection now opens RTSP, captures a fresh frame, analyzes it and closes RTSP on each scan.
- Default scan interval is now 300 seconds.
- Default stable frame count is now 1.
- Web UI frame refresh captures a fresh frame on demand.

## [0.5.0] - 2026-07-08

### Added

- Added Web UI section for an external Home Assistant collection sensor.
- Added configurable mapping from collection values to expected bin colors.
- Added expected collection attributes to the output sensor.
- Added low-light handling with `non_verificabile_buio` state.

## [0.4.0] - 2026-07-08

### Changed

- Removed manual add-on YAML options for normal use.
- Added full graphical configuration in the Ingress Web UI.
- Settings are now saved to `/data/settings.json`.
- The add-on can start before the RTSP stream is configured.

## [0.3.0] - 2026-07-08

### Added

- Added an Ingress UI to define the ROI visually from an RTSP snapshot.
- Added persistent ROI override saved from the UI.
- Added live detector reload of the saved ROI.

## [0.2.0] - 2026-07-08

### Changed

- Changed the output entity from `binary_sensor` style states to a text `sensor`.
- The sensor state now reports `grigio`, `giallo`, `blu` or `nessun_bidone`.
- Added HSV configuration for the three supported bin colors.
- Added per-color ratio diagnostics in the sensor attributes.

## [0.1.0] - 2026-07-08

### Added

- Initial Contarina Bin Detector add-on.
- RTSP stream reading with OpenCV.
- Pixel ROI monitoring.
- HSV color detection with configurable lower and upper bounds.
- Schedule filter by weekday and time window.
- Home Assistant `binary_sensor` publishing through the Supervisor Core API.
- Diagnostic attributes to help tune ROI and color thresholds.
