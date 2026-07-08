# Contarina Bin Detector Documentation

This add-on detects whether a gray, yellow or blue Contarina bin is visible in a selected area of an RTSP camera stream.

All user configuration is graphical. Use **Open Web UI** from the Home Assistant add-on page.

## First Setup

1. Install and start the add-on.
2. Open **Open Web UI**.
3. Enter the RTSP URL.
4. Keep or change the target entity, default `sensor.contarina_bidone_esposto`.
5. Configure the collection sensor entity if available.
6. Map collection values to bin colors.
7. Save the configuration.
8. Refresh the frame.
9. Draw the ROI rectangle.
10. Save again.

Settings are persisted in `/data/settings.json`.

## Scan Model

The add-on does not continuously analyze the RTSP stream. On each scan it:

1. opens the RTSP stream;
2. reads a few frames and keeps the latest one;
3. closes the RTSP stream;
4. analyzes the captured frame;
5. waits for the next scan.

The default scan interval is 300 seconds. This is intended for low-frequency checks such as verifying whether the bin has been put out.

## Web UI Sections

### Camera and Sensor

Configure:

- RTSP URL.
- Home Assistant sensor entity.
- Friendly name.
- Timezone.
- Collection sensor entity.

### Mobile Notifications

Configure:

- enable smartphone notifications;
- Home Assistant notify service, for example `notify.mobile_app_iphone`;
- notification tag;
- cooldown;
- title;
- reminder message;
- unreliable-verification message.

When the expected bin is missing, the add-on sends a reminder notification. When the expected bin is detected, it sends a `clear_notification` command with the same tag.

If the image cannot be trusted because it is dark, low-contrast or blurry, the add-on can send a dedicated notification instead of a missing-bin reminder.

Use **Test notification** to send an immediate sample notification with the current notify service.

### Expected Collection Mapping

If another Home Assistant integration exposes the expected collection with states such as `Carta`, `VPL`, `Umido` and `Secco`, enter its entity ID in the Web UI.

Then map each value to the expected bin color. Defaults:

- `Carta` -> yellow.
- `VPL` -> blue.
- `Umido` -> gray.
- `Secco` -> gray.

If no collection sensor is configured, the detector works from the time schedule. If a collection sensor is configured but its current state does not map to a color, verification is inactive and the sensor reports `nessun_bidone`.

### Schedule

Configure:

- active start time;
- active end time;
- scan interval;
- stable frame count;
- minimum brightness;
- minimum contrast;
- minimum sharpness;
- allowed weekdays.

If the schedule does not match the current time, the sensor reports `nessun_bidone`.

### Color Thresholds

Configure HSV lower and upper bounds for:

- gray;
- yellow;
- blue.

OpenCV HSV uses hue from 0 to 179 and saturation/value from 0 to 255.

The default Contarina presets are derived from the supplied CAR, SEC and VPL reference images:

- CAR/carta yellow: lower `[14, 70, 90]`, upper `[34, 255, 255]`.
- SEC/secco gray: lower `[0, 0, 55]`, upper `[179, 55, 190]`.
- VPL blue: lower `[92, 55, 50]`, upper `[118, 255, 230]`.

Use **Apply Contarina color presets** in the Web UI if existing saved settings still contain older thresholds.

### ROI

The ROI editor displays an RTSP snapshot and lets you draw the rectangle directly on the image. The saved rectangle uses the original frame pixel coordinates.

Use **Debug overlay** to capture a fresh frame with the ROI, detected state, expected collection, color ratios and image-quality values drawn on the snapshot.

## Unreliable Verification

Color detection is not reliable if the camera cannot see the bin clearly. The add-on measures:

- brightness;
- contrast;
- sharpness.

When verification is active and one of these metrics is below the configured threshold, the sensor state is:

```text
non_verificabile
```

This separates "no bin detected" from "the image is not reliable enough to trust". In practice, the best fixes are camera night mode, a small light near the bin area, cleaning/protecting the lens, or tuning the thresholds using real snapshots.

## Output

The configured entity is updated with:

- `state`: `grigio`, `giallo`, `blu`, `nessun_bidone` or `non_verificabile`.
- `detected`: whether the published state is a bin color.
- `candidate_color`: the strongest color candidate in the current scan.
- `expected_collection`: state read from the configured collection sensor.
- `expected_color`: expected bin color derived from the collection mapping.
- `expected_match`: whether the detected color matches the expected color.
- `verification_active`: whether schedule and expected collection allow verification.
- `scheduled_now`: whether today and the current time are inside the configured schedule.
- `brightness`: average ROI brightness.
- `contrast`: ROI contrast.
- `sharpness`: ROI sharpness.
- `visibility_reason`: `ok`, `buio`, `contrasto_basso`, `immagine_sfocata` or `roi_non_valida`.
- `verification_reliable`: whether the image quality is good enough for verification.
- `too_dark`: whether the current frame is below the configured brightness threshold.
- `color_ratios`: matching-pixel ratio for gray, yellow and blue.
- `min_color_ratio`: configured threshold.
- `min_brightness`: configured brightness threshold.
- `min_contrast`: configured contrast threshold.
- `min_sharpness`: configured sharpness threshold.
- `roi`: configured ROI.
- `color_ranges`: configured HSV ranges.
- `last_scan`: timestamp of the last published state change.

## Tuning Workflow

1. Use the Web UI to draw a tight ROI around the expected bin position.
2. Put one bin in view and check the `color_ratios` attribute.
3. Repeat for gray, yellow and blue.
4. Set the minimum color ratio slightly below the expected visible-bin values.
5. Check a few lighting conditions before relying on the automation.
