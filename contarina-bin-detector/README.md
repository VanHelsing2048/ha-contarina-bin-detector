# Contarina Bin Detector

Home Assistant add-on that checks an RTSP stream, analyzes a pixel area and updates a `sensor` with the color of the exposed bin.

The sensor state is one of:

- `grigio`
- `giallo`
- `blu`
- `nessun_bidone`

The state is a bin color only when:

- that color has the highest matching ratio inside the ROI;
- the ratio is above `min_color_ratio`;
- detection remains stable for `consecutive_frames`;
- the current day and time match `monitor_days`, `active_time_start` and `active_time_end`.

## Visual ROI Editor

The add-on includes a Home Assistant Ingress UI.

1. Open the add-on page.
2. Use **Open Web UI**.
3. Click **Refresh frame** if you need a new RTSP snapshot.
4. Draw a rectangle over the area where the bin appears.
5. Click **Save ROI**.

The saved ROI is stored in `/data/roi.json` and overrides the `roi` value from the add-on options. The detector reloads it while running, so a restart is not required after saving the rectangle.

## Configuration

Example:

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

`roi` uses pixel coordinates on the camera image:

- `x`, `y`: top-left corner;
- `width`, `height`: monitored area size.

You can either edit `roi` manually or use the visual ROI editor from the add-on Web UI.

`monitor_days` accepts `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun`. If the list is empty, every day is allowed.

## Color Tuning

Detection uses HSV instead of RGB because it is usually more stable when lighting changes.

Default starting values:

```yaml
gray_hsv_lower: [0, 0, 45]
gray_hsv_upper: [179, 60, 210]
yellow_hsv_lower: [18, 60, 60]
yellow_hsv_upper: [38, 255, 255]
blue_hsv_lower: [90, 50, 40]
blue_hsv_upper: [130, 255, 255]
```

The sensor attributes include `color_ratios`, so you can compare the values while each bin is visible. If the right color is not detected, lower `min_color_ratio` slightly or widen that color range. If false positives happen, tighten the ROI or raise `min_color_ratio`.

## Installation

1. Add this repository in Home Assistant from **Settings -> Add-ons -> Add-on Store -> Repositories**.
2. Install **Contarina Bin Detector**.
3. Configure RTSP, ROI, color ranges and collection days.

The add-on updates the Home Assistant entity configured in `entity_id`.
