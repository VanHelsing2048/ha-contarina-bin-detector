# Contarina Bin Detector

Home Assistant add-on that detects whether a gray, yellow or blue Contarina bin is visible in an RTSP camera area.

The add-on is configured graphically from **Open Web UI**. You do not need to edit the add-on YAML options.

The sensor state is one of:

- `grigio`
- `giallo`
- `blu`
- `nessun_bidone`
- `non_verificabile_buio`

## Graphical Configuration

1. Install and start the add-on.
2. Open the add-on page in Home Assistant.
3. Select **Open Web UI**.
4. Configure camera, sensor, expected collection, schedule, color thresholds and ROI.
5. Click **Save configuration**.

The Web UI saves settings to `/data/settings.json`. The detector reloads them while running, so most changes do not require restarting the add-on.

## Expected Collection Sensor

If another Home Assistant integration exposes the expected collection as `Carta`, `VPL`, `Umido` or `Secco`, add that entity in the **Collection sensor** field.

The Web UI lets you map each value to the expected bin color. Defaults:

- `Carta` -> yellow
- `VPL` -> blue
- `Umido` -> gray
- `Secco` -> gray

The output sensor keeps reporting the detected color, and adds attributes such as `expected_collection`, `expected_color` and `expected_match`.

## Night Handling

When the ROI brightness is below the configured minimum brightness, the sensor reports `non_verificabile_buio`. This is intentional: at night a dark frame should not be treated as a reliable `nessun_bidone`.

Best practical options:

- use the camera IR/night mode if the bin color remains distinguishable;
- add a small light or motion-triggered illumination near the ROI;
- tune **Minimum brightness** from the Web UI after checking real night frames.

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
