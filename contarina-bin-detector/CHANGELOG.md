# Changelog

Release notes for the Home Assistant add-on preview.

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
