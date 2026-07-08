# Contarina Bin Detector

Home Assistant add-on that detects whether a gray, yellow or blue Contarina bin is visible in an RTSP camera area.

The add-on is configured graphically from **Open Web UI**. You do not need to edit the add-on YAML options.

The sensor state is one of:

- `grigio`
- `giallo`
- `blu`
- `nessun_bidone`
- `non_verificabile`

## Graphical Configuration

1. Install and start the add-on.
2. Open the add-on page in Home Assistant.
3. Select **Open Web UI**.
4. Configure camera, sensor, expected collection, schedule, color thresholds and ROI.
5. Click **Save configuration**.

The Web UI saves settings to `/data/settings.json`. The detector reloads them while running, so most changes do not require restarting the add-on.

## Contarina Color Presets

The default HSV ranges are based on the provided reference images:

- CAR/carta yellow: `yellow_hsv_lower [14, 70, 90]`, `yellow_hsv_upper [34, 255, 255]`
- SEC/secco gray: `gray_hsv_lower [0, 0, 55]`, `gray_hsv_upper [179, 55, 190]`
- VPL blue: `blue_hsv_lower [92, 55, 50]`, `blue_hsv_upper [118, 255, 230]`

If the add-on already has saved settings, use **Apply Contarina color presets** in the Web UI and then save the configuration.

## Smartphone Notifications

Enable notifications in the Web UI and set the Home Assistant mobile notify service, for example:

```text
notify.mobile_app_iphone
```

When verification is active and the expected bin is not detected, the add-on sends a reminder such as `Bidone giallo da esporre oggi`. It uses a stable notification tag and cooldown to avoid repeated notifications.

When the expected bin is detected, the add-on sends a `clear_notification` command with the same tag.

Use **Test notification** in the Web UI to verify the configured `notify.mobile_app_*` service before relying on reminders.

## Scan Frequency

The detector captures a fresh RTSP frame for each scan, analyzes it, closes the RTSP stream and waits for the next scan. The default interval is 300 seconds, so one scan every 5 minutes.

The **Refresh frame** button in the Web UI also captures a fresh frame on demand.

The **Debug overlay** button captures a fresh frame and draws the ROI plus diagnostic text directly on the snapshot. It is useful for tuning color thresholds, brightness, contrast and sharpness.

## Expected Collection Sensor

If another Home Assistant integration exposes the expected collection as `Carta`, `VPL`, `Umido` or `Secco`, add that entity in the **Collection sensor** field.

The Web UI lets you map each value to the expected bin color. Defaults:

- `Carta` -> yellow
- `VPL` -> blue
- `Umido` -> gray
- `Secco` -> gray

The output sensor keeps reporting the detected color, and adds attributes such as `expected_collection`, `expected_color` and `expected_match`.

## Unreliable Verification

When the ROI is too dark, too flat/low-contrast or too blurry, the sensor reports `non_verificabile`. This is intentional: an unreadable frame should not be treated as a reliable `nessun_bidone`.

The Web UI exposes thresholds for minimum brightness, contrast and sharpness.

Best practical options:

- use the camera IR/night mode if the bin color remains distinguishable;
- add a small light or motion-triggered illumination near the ROI;
- tune brightness, contrast and sharpness from the Web UI after checking real night frames.

## Visual ROI Editor

The Web UI shows a snapshot from the configured RTSP stream.

1. Save the RTSP URL.
2. Click **Refresh frame**.
3. Draw a rectangle over the area where the bin appears.
4. Click **Save configuration**.

The rectangle is stored using the real RTSP frame pixel coordinates.

## Detection

The state is a bin color only when:

- that color has the highest matching ratio inside the ROI;
- the ratio is above the configured minimum color ratio;
- detection remains stable for the configured number of frames;
- the current day and time match the configured schedule.
- when a collection sensor is configured, the collection value maps to an expected bin color.

## Tuning

The sensor attributes include `color_ratios`, so you can compare values while each bin is visible. If the right color is not detected, lower the minimum ratio slightly or widen that color range. If false positives happen, tighten the ROI or raise the minimum ratio.
