# Contarina Bin Detector Documentation

This add-on detects whether a gray, yellow or blue Contarina bin is visible in a selected area of an RTSP camera stream.

All user configuration is graphical. Use **Open Web UI** from the Home Assistant add-on page.

## First Setup

1. Install and start the add-on.
2. Open **Open Web UI**.
3. Enter the RTSP URL.
4. Keep or change the target entity, default `sensor.contarina_bidone_esposto`.
5. Save the configuration.
6. Refresh the frame.
7. Draw the ROI rectangle.
8. Save again.

Settings are persisted in `/data/settings.json`.

## Web UI Sections

### Camera and Sensor

Configure:

- RTSP URL.
- Home Assistant sensor entity.
- Friendly name.
- Timezone.

### Schedule

Configure:

- active start time;
- active end time;
- scan interval;
- stable frame count;
- allowed weekdays.

If the schedule does not match the current time, the sensor reports `nessun_bidone`.

### Color Thresholds

Configure HSV lower and upper bounds for:

- gray;
- yellow;
- blue.

OpenCV HSV uses hue from 0 to 179 and saturation/value from 0 to 255.

### ROI

The ROI editor displays an RTSP snapshot and lets you draw the rectangle directly on the image. The saved rectangle uses the original frame pixel coordinates.

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

1. Use the Web UI to draw a tight ROI around the expected bin position.
2. Put one bin in view and check the `color_ratios` attribute.
3. Repeat for gray, yellow and blue.
4. Set the minimum color ratio slightly below the expected visible-bin values.
5. Check a few lighting conditions before relying on the automation.
