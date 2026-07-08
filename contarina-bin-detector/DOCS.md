# Contarina Bin Detector Documentation

This add-on detects whether a gray, yellow or blue Contarina bin is visible in a specific pixel area of an RTSP camera stream.

It exposes the result as a Home Assistant `sensor` whose state is:

- `grigio`
- `giallo`
- `blu`
- `nessun_bidone`

If the current day or time is outside the configured schedule, the state is `nessun_bidone` even if a matching color is visible.

## Visual ROI Editor

The add-on exposes an Ingress UI in Home Assistant. It shows a snapshot from the configured RTSP stream and lets you draw the ROI directly on the image.

Workflow:

1. Open the add-on page in Home Assistant.
2. Select **Open Web UI**.
3. Draw the rectangle over the area where the bin should appear.
4. Click **Save ROI**.

The saved rectangle is written to `/data/roi.json`. When this file exists, it overrides the `roi` values from the add-on options. The detector reloads this saved ROI while it is running.

## Configuration

```yaml
rtsp_url: rtsp://user:password@192.168.1.50:554/stream1
entity_id: sensor.contarina_bidone_esposto
device_name: Bidone Contarina
timezone: Europe/Rome
roi:
  x: 870
  y: 420
  width: 260
  height: 210
gray_hsv_lower: [0, 0, 45]
gray_hsv_upper: [179, 60, 210]
yellow_hsv_lower: [18, 60, 60]
yellow_hsv_upper: [38, 255, 255]
blue_hsv_lower: [90, 50, 40]
blue_hsv_upper: [130, 255, 255]
min_color_ratio: 0.08
consecutive_frames: 3
scan_interval: 10
monitor_days:
  - mon
active_time_start: "18:00"
active_time_end: "08:00"
```

## Options

### `rtsp_url`

RTSP stream URL for the camera.

### `entity_id`

Entity ID updated by the add-on. Use a `sensor.*` entity, for example:

```yaml
sensor.contarina_bidone_esposto
```

### `device_name`

Friendly name shown in Home Assistant.

### `timezone`

Timezone used for schedule checks. Default: `Europe/Rome`.

### `roi`

Pixel area to monitor:

- `x`: left coordinate.
- `y`: top coordinate.
- `width`: ROI width.
- `height`: ROI height.

The ROI should be as small as possible while still covering the expected bin position.

The visual ROI editor is recommended because it stores the rectangle using the real RTSP frame pixel coordinates.

### HSV color options

Each supported color has lower and upper HSV bounds:

- `gray_hsv_lower`, `gray_hsv_upper`
- `yellow_hsv_lower`, `yellow_hsv_upper`
- `blue_hsv_lower`, `blue_hsv_upper`

OpenCV HSV uses hue from 0 to 179 and saturation/value from 0 to 255.

### `min_color_ratio`

Minimum matching-pixel ratio inside the ROI. Example: `0.08` means 8 percent of the ROI must match a color before it can become the sensor state.

### `consecutive_frames`

Number of consecutive frames where the same color must be detected before the state changes.

### `scan_interval`

Seconds between scans.

### `monitor_days`

Days where detection is allowed to report a bin color.

Accepted values:

```text
mon, tue, wed, thu, fri, sat, sun
```

### `active_time_start` and `active_time_end`

Allowed time window. Overnight windows are supported, for example:

```yaml
active_time_start: "18:00"
active_time_end: "08:00"
```

## Output

The configured entity is updated with:

- `state`: `grigio`, `giallo`, `blu` or `nessun_bidone`.
- `detected`: whether the published state is a bin color.
- `candidate_color`: the strongest color candidate in the current scan.
- `scheduled_now`: whether today and the current time are inside the configured schedule.
- `color_ratios`: matching-pixel ratio for gray, yellow and blue.
- `min_color_ratio`: configured threshold.
- `roi`: configured ROI.
- `color_ranges`: configured HSV ranges.
- `last_scan`: timestamp of the last published state change.

## Tuning Workflow

1. Start with a tight ROI around the expected bin position.
2. Put one bin in view and check the `color_ratios` attribute.
3. Repeat for gray, yellow and blue.
4. Set `min_color_ratio` slightly below the expected visible-bin values.
5. Check a few lighting conditions before relying on the automation.
