# Contarina Bin Detector Documentation

This add-on detects a configured color in a specific pixel area of an RTSP camera stream and exposes the result as a Home Assistant `binary_sensor`.

It is intended for checking whether a Contarina bin is visible in the expected position on the correct collection day.

## Configuration

```yaml
rtsp_url: rtsp://user:password@192.168.1.50:554/stream1
entity_id: binary_sensor.contarina_bidone_esposto
device_name: Bidone Contarina
timezone: Europe/Rome
roi:
  x: 870
  y: 420
  width: 260
  height: 210
color_name: verde
hsv_lower: [35, 45, 35]
hsv_upper: [95, 255, 255]
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

Entity ID updated by the add-on. Use a `binary_sensor.*` entity, for example:

```yaml
binary_sensor.contarina_bidone_esposto
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

### `color_name`, `hsv_lower` and `hsv_upper`

HSV color range for the target bin color. A pixel is considered matching if it is inside the configured range.

Starting values:

```yaml
# green
color_name: verde
hsv_lower: [35, 45, 35]
hsv_upper: [95, 255, 255]

# blue
color_name: blu
hsv_lower: [90, 50, 40]
hsv_upper: [130, 255, 255]

# yellow
color_name: giallo
hsv_lower: [18, 60, 60]
hsv_upper: [38, 255, 255]

# brown / dark orange
color_name: marrone
hsv_lower: [5, 50, 30]
hsv_upper: [25, 255, 180]
```

### `min_color_ratio`

Minimum matching-pixel ratio inside the ROI. Example: `0.08` means 8 percent of the ROI must match the configured color.

Lower it if the bin is detected visually but the sensor remains off. Raise it if unrelated objects trigger the sensor.

### `consecutive_frames`

Number of consecutive positive frames required before the add-on reports detection.

### `scan_interval`

Seconds between scans.

### `monitor_days`

Days where detection is allowed to turn the sensor on.

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

- `state`: `on` or `off`.
- `detected`: whether the color threshold is currently met.
- `scheduled_now`: whether today and the current time are inside the configured schedule.
- `color_ratio`: matching-pixel ratio in the ROI.
- `roi`: configured ROI.
- `hsv_ranges`: effective color ranges used by the detector.
- `last_scan`: timestamp of the last published state change.

## Tuning Workflow

1. Start with a tight ROI around the expected bin position.
2. Use the default HSV range for the bin color.
3. Watch `color_ratio` while the bin is visible.
4. Set `min_color_ratio` slightly below the visible-bin value.
5. Check a few lighting conditions before relying on the automation.
