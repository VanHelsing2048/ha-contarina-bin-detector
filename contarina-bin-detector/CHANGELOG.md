# Changelog

Release notes for the Home Assistant add-on preview.

## [0.11.11] - 2026-07-10

### Fixed

- Fixed ROI Web UI snapshot refresh behind Home Assistant Ingress by returning cached frames quickly while RTSP capture runs in the background.
- Kept the add-on running if Home Assistant sensor publishing is temporarily unavailable.
- Removed a stray empty s6 service directory from the image.

## [0.11.10] - 2026-07-10

### Fixed

- Fixed FFmpeg snapshot capture by using the RTSP timeout option supported by the add-on image.

## [0.11.9] - 2026-07-10

### Fixed

- Fixed repeated **Refresh frame** clicks causing stale failed snapshot responses to replace a working frame.
- The Web UI now keeps the last valid frame visible when a later snapshot attempt fails.

## [0.11.8] - 2026-07-10

### Fixed

- Changed Web UI snapshot loading to use JSON image payloads instead of direct image URLs.
- Preserved detailed RTSP errors in the UI instead of falling back to the generic RTSP URL message.

## [0.11.7] - 2026-07-10

### Changed

- Use `ffmpeg` first for RTSP snapshot capture, with OpenCV as fallback.
- Include `ffmpeg` in the add-on image.

### Fixed

- Improved compatibility with H.264 RTSP cameras that OpenCV cannot open reliably.
- Redacted RTSP credentials from capture errors.

## [0.11.6] - 2026-07-10

### Added

- Added `rtsp_warmup_seconds` for cameras that need more time before returning the first RTSP frame.

### Fixed

- Snapshot capture now waits up to the configured warmup time before failing.
- The Web UI keeps the detailed RTSP error visible if the placeholder image cannot be rendered.

## [0.11.5] - 2026-07-10

### Fixed

- Fixed `Refresh frame` showing `502 Bad Gateway` when RTSP capture fails.
- Snapshot failures now render a diagnostic placeholder image and show the camera error in the Web UI.

## [0.11.4] - 2026-07-10

### Fixed

- Made the Web UI become ready faster by loading OpenCV only when snapshots or scans need it.
- Added clearer RTSP snapshot errors and an OpenCV backend fallback.
- Added a Web UI options-file diagnostic to confirm whether Home Assistant Configuration values are being read.

## [0.11.3] - 2026-07-09

### Changed

- Publish prebuilt images only for release tags or manual workflow runs.
- Added `.dockerignore` for smaller Docker build contexts and cleaner layer caching.

## [0.11.2] - 2026-07-09

### Fixed

- Fixed Configuration save errors by making the nested collection mapping schema less strict. Values are still validated by the detector at runtime.

## [0.11.1] - 2026-07-09

### Fixed

- Fixed GHCR publishing by using one prebuilt image per Home Assistant architecture.
- Kept support for `aarch64`, `amd64`, `armhf`, `armv7` and `i386` through the `{arch}` image placeholder.

## [0.11.0] - 2026-07-09

### Added

- Added prebuilt GitHub Container Registry image support so Home Assistant can pull the add-on instead of building it locally.
- Added multi-architecture image publishing for Raspberry Pi and common Home Assistant platforms.

## [0.10.1] - 2026-07-09

### Fixed

- Fixed Configuration validation errors on upgrades from older releases with empty saved options.
- Quoted schema validators and notification templates for safer Supervisor parsing.

## [0.10.0] - 2026-07-09

### Changed

- Moved fixed settings to the Home Assistant add-on Configuration tab.
- Simplified the Web UI to snapshot refresh, ROI drawing, debug overlay and notification testing.
- The Web UI now saves only ROI data while the detector reads fixed options from `/data/options.json`.

## [0.9.2] - 2026-07-09

### Fixed

- Added `init: false` to fix `s6-overlay-suexec: fatal: can only run as pid 1` on Home Assistant systems using s6 overlay v3 base images.

## [0.9.1] - 2026-07-09

### Fixed

- Fixed `s6-overlay-suexec: fatal: can only run as pid 1` by running the detector as an s6 service instead of overriding the container command.

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
