# Changelog

All notable changes to this repository are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses semantic versioning.

## [0.11.13] - 2026-07-11

### Added

- Added a live status panel to the Web UI showing current ROI detection values, color ratios, image quality metrics, and the configured collection forecast sensor state.

## [0.11.12] - 2026-07-11

### Fixed

- Fixed the s6 service launcher so Home Assistant Supervisor environment variables, including `SUPERVISOR_TOKEN`, are available to the detector process.

## [0.11.11] - 2026-07-10

### Fixed

- Fixed Web UI snapshot refresh through Home Assistant Ingress by serving the latest cached frame instead of blocking the HTTP request on a live RTSP capture.
- Kept the detector loop alive if publishing the sensor state to Home Assistant fails temporarily.
- Removed an empty service directory that caused noisy s6 service warnings.

## [0.11.10] - 2026-07-10

### Fixed

- Fixed FFmpeg RTSP capture by using the supported `-timeout` option instead of unsupported timeout flags.

## [0.11.9] - 2026-07-10

### Fixed

- Prevented older or failed snapshot refresh requests from overwriting a newer successful frame in the Web UI.
- Disabled snapshot buttons while a capture is in progress and kept the last valid frame visible when later captures fail.

## [0.11.8] - 2026-07-10

### Fixed

- Changed Web UI snapshot loading to use JSON image payloads, avoiding Ingress/browser image-load fallback messages.
- Snapshot errors now remain visible in the Web UI even when the placeholder image cannot be rendered.

## [0.11.7] - 2026-07-10

### Changed

- Use `ffmpeg` as the primary RTSP frame capture path and keep OpenCV as fallback.
- Add the `ffmpeg` package to prebuilt add-on images.

### Fixed

- Improved compatibility with H.264 RTSP cameras that answer DESCRIBE correctly but fail to provide frames through OpenCV capture.
- Redact RTSP credentials from capture errors shown in logs or the Web UI.

## [0.11.6] - 2026-07-10

### Added

- Added `rtsp_warmup_seconds` to allow slower RTSP cameras to deliver their first frame.

### Fixed

- Snapshot capture now waits for a frame until the warmup timeout instead of giving up after only a few reads.
- The Web UI now preserves the detailed RTSP error instead of replacing it with a generic image-load message.

## [0.11.5] - 2026-07-10

### Fixed

- Prevented Home Assistant Ingress from showing `502 Bad Gateway` on snapshot failures.
- Snapshot and debug endpoints now return a diagnostic placeholder image with the RTSP/OpenCV error.

## [0.11.4] - 2026-07-10

### Fixed

- Improved Web UI readiness by lazy-loading OpenCV only when camera capture is needed.
- Improved RTSP diagnostics with clearer snapshot errors and a fallback OpenCV capture backend.
- Added Web UI diagnostics for whether Home Assistant options are loaded.

## [0.11.3] - 2026-07-09

### Changed

- Publish GHCR images only for release tags or manual workflow runs, avoiding duplicate image builds on every push to `main`.
- Added a Docker ignore file to keep the add-on build context small and cache-friendly.

## [0.11.2] - 2026-07-09

### Fixed

- Relaxed nested collection mapping schema values from enum selectors to strings to avoid Home Assistant `not a valid value` save errors.

## [0.11.1] - 2026-07-09

### Fixed

- Switched prebuilt images to Home Assistant's `{arch}` image naming pattern so all declared add-on architectures can use the correct base image.
- Fixed GitHub Actions publishing by building one image per Home Assistant architecture.

## [0.11.0] - 2026-07-09

### Added

- Added GitHub Container Registry image support for faster Home Assistant updates.
- Added multi-architecture prebuilt image publishing for `aarch64`, `amd64`, `armhf`, `armv7` and `i386`.

## [0.10.1] - 2026-07-09

### Fixed

- Made the add-on Configuration schema tolerant of missing options on upgrades from older `schema: false` releases.
- Quoted schema validators and notification templates to avoid YAML/Supervisor parsing ambiguity.

## [0.10.0] - 2026-07-09

### Changed

- Moved stable configuration back to the Home Assistant add-on Configuration tab with a schema.
- Simplified the Web UI so it only handles ROI drawing, snapshot refresh, debug overlay and notification testing.
- The Web UI now persists only the ROI in `/data/settings.json`; fixed options are read from `/data/options.json`.

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
