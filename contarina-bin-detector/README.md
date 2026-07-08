# Contarina Bin Detector

Home Assistant add-on that checks an RTSP stream, analyzes a pixel area and updates a `binary_sensor` when the configured bin color is visible on the correct collection day.

The sensor is `on` only when:

- the matching color ratio inside the ROI is above `min_color_ratio`;
- detection remains positive for `consecutive_frames`;
- the current day and time match `monitor_days`, `active_time_start` and `active_time_end`.

## Configuration

Example:

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

`roi` uses pixel coordinates on the camera image:

- `x`, `y`: top-left corner;
- `width`, `height`: monitored area size.

`monitor_days` accepts `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun`. If the list is empty, every day is allowed.

## Color Tuning

Detection uses HSV instead of RGB because it is usually more stable when lighting changes.

Useful starting values:

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

If the sensor stays off while the bin is visible, lower `min_color_ratio` slightly or enlarge the ROI. If similar objects trigger it, tighten the ROI or raise `min_color_ratio`.

## Installation

1. Add this repository in Home Assistant from **Settings -> Add-ons -> Add-on Store -> Repositories**.
2. Install **Contarina Bin Detector**.
3. Configure RTSP, ROI, color and collection days.

The add-on updates the Home Assistant entity configured in `entity_id`.
