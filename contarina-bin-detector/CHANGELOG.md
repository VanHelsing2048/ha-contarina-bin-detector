# Changelog

Release notes for the Home Assistant add-on preview.

## [0.9.0] - 2026-07-08

### Added

- Added **Test notification** in the Web UI for the configured smartphone notify service.
- Added **Debug overlay** in the Web UI with ROI rectangle, detected state, expected collection, color ratios and image-quality diagnostics.

## [0.8.0] - 2026-07-08

### Changed

- Updated gray, yellow and blue HSV defaults from the provided Contarina reference images.
- Added **Apply Contarina color presets** in the Web UI.

## [0.7.0] - 2026-07-08

### Added

- Added smartphone notifications through a configured Home Assistant notify service.
- Added notification cooldown and stable tag-based notification replacement.
- Added automatic mobile notification clearing when the expected bin is detected.
- Added unreliable-verification notifications for dark, low-contrast or blurry images.
- Added add-on icon.

### Fixed

- Fixed startup by using a `run.sh` command instead of launching Python directly.

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
