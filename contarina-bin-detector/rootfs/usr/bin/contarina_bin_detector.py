#!/usr/bin/env python3
from __future__ import annotations

import base64
import importlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, time as day_time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo


class LazyModule:
    def __init__(self, module_name: str) -> None:
        self.module_name = module_name
        self.module: Any = None

    def __getattr__(self, name: str) -> Any:
        if self.module is None:
            self.module = importlib.import_module(self.module_name)
        return getattr(self.module, name)


cv2 = LazyModule("cv2")
np = LazyModule("numpy")
requests = LazyModule("requests")


OPTIONS_PATH = "/data/options.json"
SETTINGS_PATH = "/data/settings.json"
NOTIFICATION_STATE_PATH = "/data/notification_state.json"
CORE_API_BASE = "http://supervisor/core/api"
UI_PORT = 8099
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
COLORS = ("gray", "yellow", "blue")
STATE_NAMES = {
    "gray": "grigio",
    "yellow": "giallo",
    "blue": "blu",
}
NONE_STATE = "nessun_bidone"
UNRELIABLE_STATE = "non_verificabile"
CONTARINA_COLOR_PRESETS = {
    "gray": {
        "lower": [0, 0, 55],
        "upper": [179, 55, 190],
    },
    "yellow": {
        "lower": [14, 70, 90],
        "upper": [34, 255, 255],
    },
    "blue": {
        "lower": [92, 55, 50],
        "upper": [118, 255, 230],
    },
}
LATEST_FRAME: np.ndarray | None = None
LATEST_FRAME_LOCK = Lock()

DEFAULT_SETTINGS: dict[str, Any] = {
    "rtsp_url": "",
    "entity_id": "sensor.contarina_bidone_esposto",
    "device_name": "Bidone Contarina",
    "collection_sensor_entity": "",
    "collection_mapping": {
        "Carta": "yellow",
        "VPL": "blue",
        "Umido": "gray",
        "Secco": "gray",
    },
    "timezone": "Europe/Rome",
    "roi": {"x": 100, "y": 100, "width": 300, "height": 250},
    "gray_hsv_lower": CONTARINA_COLOR_PRESETS["gray"]["lower"],
    "gray_hsv_upper": CONTARINA_COLOR_PRESETS["gray"]["upper"],
    "yellow_hsv_lower": CONTARINA_COLOR_PRESETS["yellow"]["lower"],
    "yellow_hsv_upper": CONTARINA_COLOR_PRESETS["yellow"]["upper"],
    "blue_hsv_lower": CONTARINA_COLOR_PRESETS["blue"]["lower"],
    "blue_hsv_upper": CONTARINA_COLOR_PRESETS["blue"]["upper"],
    "min_color_ratio": 0.08,
    "min_brightness": 35,
    "min_contrast": 15,
    "min_sharpness": 20,
    "consecutive_frames": 1,
    "scan_interval": 300,
    "rtsp_warmup_seconds": 20,
    "monitor_days": ["mon"],
    "active_time_start": "00:00",
    "active_time_end": "23:59",
    "notify_enabled": False,
    "notify_service": "",
    "notify_tag": "contarina_bin_reminder",
    "notify_cooldown": 3600,
    "notify_unreliable": True,
    "notify_title": "Bidone da esporre",
    "notify_message": "Bidone {color} da esporre oggi.",
    "notify_unreliable_message": "Non riesco a verificare il bidone: {reason}.",
}


def log(message: str) -> None:
    print(message, flush=True)


def redact_rtsp_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if parsed.scheme.lower() != "rtsp" or "@" not in parsed.netloc:
        return value
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, f"***:***@{host}", parsed.path, parsed.query, parsed.fragment))


def sanitize_capture_error(message: str, rtsp_url: str) -> str:
    redacted = redact_rtsp_url(rtsp_url)
    return message.replace(rtsp_url, redacted)


def load_settings() -> dict[str, Any]:
    settings = json.loads(json.dumps(DEFAULT_SETTINGS))
    if os.path.exists(OPTIONS_PATH):
        try:
            with open(OPTIONS_PATH, "r", encoding="utf-8") as options_file:
                options = json.load(options_file)
            settings.update({key: value for key, value in options.items() if value is not None})
        except Exception as error:
            log(f"Ignoring invalid options file: {error}")

    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as settings_file:
                saved = json.load(settings_file)
            if "roi" in saved:
                settings["roi"] = saved["roi"]
        except Exception as error:
            log(f"Ignoring invalid settings file: {error}")

    settings["roi"] = validate_roi(settings["roi"])
    for color in COLORS:
        settings[f"{color}_hsv_lower"] = validate_hsv(settings[f"{color}_hsv_lower"])
        settings[f"{color}_hsv_upper"] = validate_hsv(settings[f"{color}_hsv_upper"])
    settings["monitor_days"] = validate_monitor_days(settings.get("monitor_days", []))
    settings["collection_mapping"] = validate_collection_mapping(settings.get("collection_mapping", {}))
    settings["min_color_ratio"] = max(0.0, min(1.0, float(settings.get("min_color_ratio", 0.08))))
    settings["min_brightness"] = max(0, min(255, int(settings.get("min_brightness", 35))))
    settings["min_contrast"] = max(0, float(settings.get("min_contrast", 15)))
    settings["min_sharpness"] = max(0, float(settings.get("min_sharpness", 20)))
    settings["consecutive_frames"] = max(1, int(settings.get("consecutive_frames", 1)))
    settings["scan_interval"] = max(1, int(settings.get("scan_interval", 300)))
    settings["rtsp_warmup_seconds"] = max(1, int(settings.get("rtsp_warmup_seconds", 20)))
    settings["notify_enabled"] = bool(settings.get("notify_enabled", False))
    settings["notify_unreliable"] = bool(settings.get("notify_unreliable", True))
    settings["notify_cooldown"] = max(60, int(settings.get("notify_cooldown", 3600)))
    settings["_diagnostics"] = {
        "options_file": os.path.exists(OPTIONS_PATH),
        "settings_file": os.path.exists(SETTINGS_PATH),
        "rtsp_configured": bool(str(settings.get("rtsp_url", "")).strip()),
    }
    return settings


def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    merged = load_settings()
    merged["roi"] = validate_roi(settings.get("roi", merged["roi"]))

    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as settings_file:
        json.dump({"roi": merged["roi"]}, settings_file, indent=2)
        settings_file.write("\n")
    return merged


def validate_roi(roi: dict[str, Any]) -> dict[str, int]:
    return {
        "x": max(0, int(roi["x"])),
        "y": max(0, int(roi["y"])),
        "width": max(1, int(roi["width"])),
        "height": max(1, int(roi["height"])),
    }


def validate_hsv(value: list[Any]) -> list[int]:
    if isinstance(value, str):
        value = [part.strip() for part in value.split(",")]
    hue = max(0, min(179, int(value[0])))
    saturation = max(0, min(255, int(value[1])))
    brightness = max(0, min(255, int(value[2])))
    return [hue, saturation, brightness]


def validate_monitor_days(value: Any) -> list[str]:
    if isinstance(value, str):
        days = [day.strip().lower() for day in value.split(",")]
    else:
        days = [str(day).strip().lower() for day in value]
    return [day for day in days if day in WEEKDAYS]


def validate_collection_mapping(mapping: dict[str, Any]) -> dict[str, str]:
    defaults = DEFAULT_SETTINGS["collection_mapping"]
    validated = {}
    for label, default_color in defaults.items():
        color = str(mapping.get(label, default_color))
        validated[label] = color if color in COLORS else default_color
    return validated


def parse_clock(value: str) -> day_time:
    hour, minute = value.split(":", 1)
    return day_time(int(hour), int(minute))


def is_time_in_window(now: datetime, start: str, end: str) -> bool:
    current = now.time()
    start_time = parse_clock(start)
    end_time = parse_clock(end)
    if start_time <= end_time:
        return start_time <= current <= end_time
    return current >= start_time or current <= end_time


def is_scheduled_now(settings: dict[str, Any]) -> bool:
    timezone = ZoneInfo(settings.get("timezone", "Europe/Rome"))
    now = datetime.now(timezone)
    monitor_days = [day.lower() for day in settings.get("monitor_days", [])]
    day_matches = not monitor_days or WEEKDAYS[now.weekday()] in monitor_days
    time_matches = is_time_in_window(
        now,
        settings.get("active_time_start", "00:00"),
        settings.get("active_time_end", "23:59"),
    )
    return day_matches and time_matches


def crop_roi(frame: np.ndarray, roi: dict[str, int]) -> np.ndarray:
    height, width = frame.shape[:2]
    x1 = max(0, min(width, int(roi["x"])))
    y1 = max(0, min(height, int(roi["y"])))
    x2 = max(x1, min(width, x1 + int(roi["width"])))
    y2 = max(y1, min(height, y1 + int(roi["height"])))
    return frame[y1:y2, x1:x2]


def color_ratios(frame: np.ndarray, settings: dict[str, Any]) -> dict[str, float]:
    region = crop_roi(frame, settings["roi"])
    if region.size == 0:
        return {color: 0.0 for color in COLORS}

    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    ratios = {}
    for color, hsv_range in configured_color_ranges(settings).items():
        lower = np.array(hsv_range["lower"], dtype=np.uint8)
        upper = np.array(hsv_range["upper"], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)
        ratios[color] = float(cv2.countNonZero(mask)) / float(mask.size)
    return ratios


def roi_quality(frame: np.ndarray, settings: dict[str, Any]) -> dict[str, Any]:
    region = crop_roi(frame, settings["roi"])
    if region.size == 0:
        return {
            "brightness": 0.0,
            "contrast": 0.0,
            "sharpness": 0.0,
            "reliable": False,
            "reason": "roi_non_valida",
        }

    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(hsv[:, :, 2]))
    contrast = float(np.std(gray))
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    if brightness < int(settings["min_brightness"]):
        reason = "buio"
    elif contrast < float(settings["min_contrast"]):
        reason = "contrasto_basso"
    elif sharpness < float(settings["min_sharpness"]):
        reason = "immagine_sfocata"
    else:
        reason = "ok"

    return {
        "brightness": brightness,
        "contrast": contrast,
        "sharpness": sharpness,
        "reliable": reason == "ok",
        "reason": reason,
    }


def configured_color_ranges(settings: dict[str, Any]) -> dict[str, dict[str, list[int]]]:
    return {
        color: {
            "lower": settings[f"{color}_hsv_lower"],
            "upper": settings[f"{color}_hsv_upper"],
        }
        for color in COLORS
    }


def detected_color(ratios: dict[str, float], min_ratio: float) -> str:
    color = max(ratios, key=ratios.get)
    if ratios[color] >= min_ratio:
        return STATE_NAMES[color]
    return NONE_STATE


def home_assistant_get_state(entity_id: str) -> dict[str, Any] | None:
    entity_id = entity_id.strip()
    if not entity_id:
        return None

    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return None

    response = requests.get(
        f"{CORE_API_BASE}/states/{entity_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if response.status_code == HTTPStatus.NOT_FOUND:
        return None
    response.raise_for_status()
    return response.json()


def home_assistant_call_service(domain: str, service: str, payload: dict[str, Any]) -> None:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise RuntimeError("SUPERVISOR_TOKEN is not available.")

    response = requests.post(
        f"{CORE_API_BASE}/services/{domain}/{service}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=10,
    )
    response.raise_for_status()


def expected_collection(settings: dict[str, Any]) -> dict[str, Any]:
    entity_id = settings.get("collection_sensor_entity", "").strip()
    if not entity_id:
        return {
            "entity_id": "",
            "state": "",
            "expected_color": "",
            "expected_state": "",
            "verification_active": True,
        }

    entity_state = home_assistant_get_state(entity_id)
    collection_state = "" if entity_state is None else str(entity_state.get("state", ""))
    mapping = settings.get("collection_mapping", {})
    expected_color = ""
    for label, color in mapping.items():
        if collection_state.lower() == str(label).lower():
            expected_color = color
            break

    return {
        "entity_id": entity_id,
        "state": collection_state,
        "expected_color": expected_color,
        "expected_state": STATE_NAMES.get(expected_color, ""),
        "verification_active": bool(expected_color),
    }


def publish_state(
    settings: dict[str, Any],
    state: str,
    candidate_color: str,
    ratios: dict[str, float],
    scheduled: bool,
    collection: dict[str, Any],
    quality: dict[str, Any],
) -> None:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise RuntimeError("SUPERVISOR_TOKEN is not available.")

    payload = {
        "state": state,
        "attributes": {
            "friendly_name": settings.get("device_name", "Bidone Contarina"),
            "detected": state in STATE_NAMES.values(),
            "candidate_color": candidate_color,
            "expected_collection": collection["state"],
            "expected_color": collection["expected_state"],
            "expected_match": bool(collection["expected_state"] and state == collection["expected_state"]),
            "verification_active": bool(scheduled and collection["verification_active"]),
            "scheduled_now": scheduled,
            "verification_reliable": bool(quality["reliable"]),
            "visibility_reason": quality["reason"],
            "brightness": round(float(quality["brightness"]), 1),
            "contrast": round(float(quality["contrast"]), 1),
            "sharpness": round(float(quality["sharpness"]), 1),
            "too_dark": quality["reason"] == "buio",
            "color_ratios": {color: round(ratio, 4) for color, ratio in ratios.items()},
            "min_color_ratio": float(settings["min_color_ratio"]),
            "min_brightness": int(settings["min_brightness"]),
            "min_contrast": float(settings["min_contrast"]),
            "min_sharpness": float(settings["min_sharpness"]),
            "roi": settings["roi"],
            "color_ranges": configured_color_ranges(settings),
            "last_scan": datetime.now(ZoneInfo(settings.get("timezone", "Europe/Rome"))).isoformat(),
        },
    }
    response = requests.post(
        f"{CORE_API_BASE}/states/{settings['entity_id']}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=10,
    )
    response.raise_for_status()


def load_notification_state() -> dict[str, Any]:
    if not os.path.exists(NOTIFICATION_STATE_PATH):
        return {}
    try:
        with open(NOTIFICATION_STATE_PATH, "r", encoding="utf-8") as state_file:
            return json.load(state_file)
    except Exception as error:
        log(f"Ignoring invalid notification state: {error}")
        return {}


def save_notification_state(state: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(NOTIFICATION_STATE_PATH), exist_ok=True)
    with open(NOTIFICATION_STATE_PATH, "w", encoding="utf-8") as state_file:
        json.dump(state, state_file, indent=2)
        state_file.write("\n")


def notify_service_parts(settings: dict[str, Any]) -> tuple[str, str] | None:
    notify_service = settings.get("notify_service", "").strip()
    if not notify_service:
        return None
    if notify_service.startswith("notify."):
        notify_service = notify_service.split(".", 1)[1]
    return "notify", notify_service


def send_mobile_notification(settings: dict[str, Any], title: str, message: str, tag: str) -> None:
    parts = notify_service_parts(settings)
    if not parts:
        return
    domain, service = parts
    home_assistant_call_service(
        domain,
        service,
        {
            "title": title,
            "message": message,
            "data": {
                "tag": tag,
                "channel": "Contarina",
            },
        },
    )


def send_test_notification(settings: dict[str, Any]) -> None:
    if not notify_service_parts(settings):
        raise RuntimeError("Configure the notify service first.")
    tag = f"{settings.get('notify_tag', 'contarina_bin_reminder')}_test"
    send_mobile_notification(
        settings,
        "Contarina test",
        "Notifica di prova dal Contarina Bin Detector.",
        tag,
    )


def clear_mobile_notification(settings: dict[str, Any], tag: str) -> None:
    parts = notify_service_parts(settings)
    if not parts:
        return
    domain, service = parts
    home_assistant_call_service(
        domain,
        service,
        {
            "message": "clear_notification",
            "data": {"tag": tag},
        },
    )


def format_notification_template(template: str, collection: dict[str, Any], reason: str = "") -> str:
    return template.format(
        color=collection.get("expected_state", ""),
        collection=collection.get("state", ""),
        reason=reason,
    )


def manage_mobile_notification(
    settings: dict[str, Any],
    state: str,
    collection: dict[str, Any],
    scheduled: bool,
    quality: dict[str, Any],
) -> None:
    if not settings.get("notify_enabled", False):
        return
    if not scheduled or not collection.get("verification_active"):
        return
    if not collection.get("expected_state"):
        return
    if not notify_service_parts(settings):
        return

    tag = settings.get("notify_tag", "contarina_bin_reminder")
    now = time.time()
    notification_state = load_notification_state()
    expected_state = collection.get("expected_state", "")
    notification_key = f"{collection.get('state', '')}:{expected_state}:{state}"

    if expected_state and state == expected_state:
        clear_mobile_notification(settings, tag)
        save_notification_state({"active": False, "last_key": "", "last_sent": now})
        log("Cleared mobile notification because the expected bin was detected")
        return

    unreliable = state == UNRELIABLE_STATE
    if unreliable and not settings.get("notify_unreliable", True):
        return

    cooldown = max(60, int(settings.get("notify_cooldown", 3600)))
    if (
        notification_state.get("active")
        and notification_state.get("last_key") == notification_key
        and now - float(notification_state.get("last_sent", 0)) < cooldown
    ):
        return

    title = settings.get("notify_title", "Bidone da esporre")
    if unreliable:
        message = format_notification_template(
            settings.get("notify_unreliable_message", "Non riesco a verificare il bidone: {reason}."),
            collection,
            str(quality["reason"]).replace("_", " "),
        )
    else:
        message = format_notification_template(
            settings.get("notify_message", "Bidone {color} da esporre oggi."),
            collection,
        )

    send_mobile_notification(settings, title, message, tag)
    save_notification_state({"active": True, "last_key": notification_key, "last_sent": now})
    log(f"Sent mobile notification: {message}")


def open_stream(rtsp_url: str) -> cv2.VideoCapture:
    rtsp_url = rtsp_url.strip()
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|stimeout;10000000")
    capture = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    if not capture.isOpened():
        capture.release()
        capture = cv2.VideoCapture(rtsp_url)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return capture


def capture_snapshot(settings: dict[str, Any]) -> bytes:
    rtsp_url = settings["rtsp_url"]
    if not rtsp_url.strip():
        raise RuntimeError("Configure the RTSP URL first.")

    frame = capture_fresh_frame(rtsp_url.strip(), float(settings.get("rtsp_warmup_seconds", 20)))
    with LATEST_FRAME_LOCK:
        global LATEST_FRAME
        LATEST_FRAME = frame.copy()
    return encode_snapshot(frame)


def capture_debug_snapshot(settings: dict[str, Any]) -> bytes:
    rtsp_url = settings["rtsp_url"].strip()
    if not rtsp_url:
        raise RuntimeError("Configure the RTSP URL first.")

    frame = capture_fresh_frame(rtsp_url, float(settings.get("rtsp_warmup_seconds", 20)))
    with LATEST_FRAME_LOCK:
        global LATEST_FRAME
        LATEST_FRAME = frame.copy()

    state, candidate_color, _, _, collection, ratios, quality, scheduled = analyze_frame(
        frame,
        settings,
        NONE_STATE,
        0,
    )
    draw_debug_overlay(frame, settings, state, candidate_color, collection, ratios, quality, scheduled)
    return encode_snapshot(frame)


def capture_fresh_frame(rtsp_url: str, warmup_seconds: float = 20.0) -> np.ndarray:
    try:
        return capture_fresh_frame_with_ffmpeg(rtsp_url, warmup_seconds)
    except Exception as ffmpeg_error:
        ffmpeg_message = sanitize_capture_error(str(ffmpeg_error), rtsp_url)
        log(f"FFmpeg RTSP capture failed, trying OpenCV fallback: {ffmpeg_message}")
        try:
            return capture_fresh_frame_with_opencv(rtsp_url, warmup_seconds)
        except Exception as opencv_error:
            opencv_message = sanitize_capture_error(str(opencv_error), rtsp_url)
            raise RuntimeError(f"FFmpeg failed: {ffmpeg_message}; OpenCV failed: {opencv_message}") from opencv_error


def capture_fresh_frame_with_ffmpeg(rtsp_url: str, warmup_seconds: float) -> np.ndarray:
    timeout = max(5.0, warmup_seconds + 5.0)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-rtsp_transport",
        "tcp",
        "-timeout",
        str(int(max(1.0, warmup_seconds) * 1_000_000)),
        "-analyzeduration",
        "5000000",
        "-probesize",
        "1000000",
        "-i",
        rtsp_url,
        "-frames:v",
        "1",
        "-an",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    ]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"ffmpeg timed out after {timeout:.0f}s") from error
    if result.returncode != 0:
        error = sanitize_capture_error(result.stderr.decode("utf-8", errors="replace").strip(), rtsp_url)
        raise RuntimeError(error or f"ffmpeg exited with status {result.returncode}")
    if not result.stdout:
        raise RuntimeError("ffmpeg did not return an image")

    image = np.frombuffer(result.stdout, dtype=np.uint8)
    frame = cv2.imdecode(image, cv2.IMREAD_COLOR)
    if frame is None:
        raise RuntimeError("ffmpeg returned an image that OpenCV could not decode")
    return frame


def capture_fresh_frame_with_opencv(rtsp_url: str, warmup_seconds: float) -> np.ndarray:
    capture = open_stream(rtsp_url)
    try:
        if not capture.isOpened():
            raise RuntimeError("RTSP stream could not be opened by OpenCV")

        frame = None
        attempts = 0
        deadline = time.monotonic() + max(1.0, warmup_seconds)
        while time.monotonic() < deadline:
            attempts += 1
            ok, candidate = capture.read()
            if ok and candidate is not None:
                frame = candidate
                break
            time.sleep(0.2)

        if frame is None:
            raise RuntimeError(f"RTSP stream opened but no frame could be read within {warmup_seconds:.0f}s ({attempts} attempts)")

        return frame
    finally:
        capture.release()


def draw_debug_overlay(
    frame: np.ndarray,
    settings: dict[str, Any],
    state: str,
    candidate_color: str,
    collection: dict[str, Any],
    ratios: dict[str, float],
    quality: dict[str, Any],
    scheduled: bool,
) -> None:
    roi = validate_roi(settings["roi"])
    height, width = frame.shape[:2]
    x1 = max(0, min(width - 1, roi["x"]))
    y1 = max(0, min(height - 1, roi["y"]))
    x2 = max(x1 + 1, min(width, roi["x"] + roi["width"]))
    y2 = max(y1 + 1, min(height, roi["y"] + roi["height"]))

    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 215, 255), 3)
    overlay_lines = [
        f"state: {state}",
        f"candidate: {candidate_color}",
        f"expected: {collection.get('expected_state', '') or '-'} ({collection.get('state', '') or '-'})",
        f"scheduled: {scheduled}",
        "ratios: " + ", ".join(f"{color}={ratio:.3f}" for color, ratio in ratios.items()),
        f"quality: {quality['reason']} b={float(quality['brightness']):.1f} c={float(quality['contrast']):.1f} s={float(quality['sharpness']):.1f}",
    ]

    line_height = 24
    box_height = 12 + line_height * len(overlay_lines)
    box_width = min(width - 20, 820)
    cv2.rectangle(frame, (10, 10), (10 + box_width, 10 + box_height), (0, 0, 0), -1)
    cv2.rectangle(frame, (10, 10), (10 + box_width, 10 + box_height), (255, 255, 255), 1)
    for index, line in enumerate(overlay_lines):
        y = 35 + index * line_height
        cv2.putText(frame, line, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 1, cv2.LINE_AA)


def encode_snapshot(frame: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise RuntimeError("Could not encode snapshot")
    return encoded.tobytes()


def xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def error_image(message: str) -> bytes:
    safe_message = xml_escape(message)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540">
  <rect width="960" height="540" fill="#101418"/>
  <rect x="32" y="32" width="896" height="476" fill="#172027" stroke="#40515f" stroke-width="2"/>
  <text x="64" y="104" fill="#eef2f4" font-family="Arial, sans-serif" font-size="34" font-weight="700">Snapshot unavailable</text>
  <text x="64" y="158" fill="#f5c542" font-family="Arial, sans-serif" font-size="22">{safe_message}</text>
  <text x="64" y="220" fill="#bcc8cf" font-family="Arial, sans-serif" font-size="18">Check the add-on Configuration tab and the RTSP camera logs.</text>
</svg>"""
    return svg.encode("utf-8")


class WebUiHandler(BaseHTTPRequestHandler):
    server_version = "ContarinaWebUi/0.11.9"

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self.send_html(web_ui_html())
            return
        if self.path.startswith("/api/snapshot"):
            self.send_snapshot_json(debug=False)
            return
        if self.path.startswith("/api/debug-snapshot"):
            self.send_snapshot_json(debug=True)
            return
        if self.path.startswith("/snapshot"):
            self.send_snapshot()
            return
        if self.path.startswith("/debug-snapshot"):
            self.send_debug_snapshot()
            return
        if self.path.startswith("/api/settings"):
            self.send_json(load_settings())
            return
        if self.path.startswith("/api/color-presets"):
            self.send_json(CONTARINA_COLOR_PRESETS)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path.startswith("/api/settings"):
            payload = self.read_json_body()
            saved = save_settings(payload)
            self.send_json({"ok": True, "settings": saved})
            log("Saved settings from Web UI")
            return
        if self.path.startswith("/api/test-notification"):
            settings = load_settings()
            try:
                send_test_notification(settings)
            except Exception as error:
                self.send_error(HTTPStatus.BAD_REQUEST, str(error))
                return
            self.send_json({"ok": True})
            log("Sent test notification from Web UI")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        log(f"Web UI: {format % args}")

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        return json.loads(body.decode("utf-8"))

    def send_html(self, html: str) -> None:
        data = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_image(self, data: bytes, content_type: str, error: str = "") -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        if error:
            self.send_header("X-Contarina-Error", error)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_snapshot(self) -> None:
        try:
            data = capture_snapshot(load_settings())
        except Exception as error:
            message = str(error)
            self.send_image(error_image(message), "image/svg+xml", message)
            return

        self.send_image(data, "image/jpeg")

    def send_debug_snapshot(self) -> None:
        try:
            data = capture_debug_snapshot(load_settings())
        except Exception as error:
            message = str(error)
            self.send_image(error_image(message), "image/svg+xml", message)
            return

        self.send_image(data, "image/jpeg")

    def send_snapshot_json(self, debug: bool) -> None:
        try:
            if debug:
                data = capture_debug_snapshot(load_settings())
            else:
                data = capture_snapshot(load_settings())
            self.send_json(
                {
                    "ok": True,
                    "content_type": "image/jpeg",
                    "image": base64.b64encode(data).decode("ascii"),
                    "error": "",
                }
            )
        except Exception as error:
            message = str(error)
            data = error_image(message)
            self.send_json(
                {
                    "ok": False,
                    "content_type": "image/svg+xml",
                    "image": base64.b64encode(data).decode("ascii"),
                    "error": message,
                }
            )


def web_ui_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Contarina Bin Detector</title>
  <style>
    :root { color-scheme: light dark; font-family: system-ui, sans-serif; }
    body { margin: 0; background: #101418; color: #eef2f4; }
    main { max-width: 1180px; margin: 0 auto; padding: 16px; }
    h1 { font-size: 22px; margin: 0 0 16px; font-weight: 650; }
    h2 { font-size: 16px; margin: 0 0 12px; }
    section { border-top: 1px solid #2d3a43; padding: 16px 0; }
    label { display: grid; gap: 6px; color: #c9d4da; font-size: 13px; }
    input, select { box-sizing: border-box; width: 100%; border: 1px solid #3d4d58; border-radius: 6px; padding: 9px 10px; background: #172027; color: #eef2f4; }
    input[type="checkbox"] { width: auto; }
    button { border: 0; border-radius: 6px; padding: 9px 12px; background: #46a758; color: white; font-weight: 650; cursor: pointer; }
    button.secondary { background: #40515f; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    .stage { position: relative; display: inline-block; max-width: 100%; background: #050708; border: 1px solid #2d3a43; }
    img { display: block; max-width: 100%; height: auto; user-select: none; }
    canvas { position: absolute; inset: 0; width: 100%; height: 100%; cursor: crosshair; }
    .status { margin-top: 12px; color: #bcc8cf; font-size: 14px; }
    .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 8px; color: #c9d4da; font-size: 13px; }
    code { color: #d8e7ff; }
  </style>
</head>
<body>
  <main>
    <h1>Contarina Bin Detector</h1>
    <section>
      <h2>Configured in Home Assistant</h2>
      <div class="summary" id="summary"></div>
      <div class="row" style="margin-top: 12px;">
        <button class="secondary" id="test_notification" type="button">Test notification</button>
      </div>
    </section>
    <section>
      <div class="row">
        <h2>ROI</h2>
        <button class="secondary" id="refresh" type="button">Refresh frame</button>
        <button class="secondary" id="debug" type="button">Debug overlay</button>
        <button id="save" type="button">Save ROI</button>
      </div>
      <div class="stage">
        <img id="snapshot" alt="RTSP snapshot">
        <canvas id="overlay"></canvas>
      </div>
      <div class="status" id="status">Loading configuration...</div>
    </section>
  </main>
  <script>
    const img = document.getElementById("snapshot");
    const canvas = document.getElementById("overlay");
    const ctx = canvas.getContext("2d");
    const statusEl = document.getElementById("status");
    const summaryEl = document.getElementById("summary");
    const refreshButton = document.getElementById("refresh");
    const debugButton = document.getElementById("debug");
    let settings = null;
    let drawing = false;
    let start = null;
    let lastSnapshotError = "";
    let snapshotRequestId = 0;

    function setStatus(message) {
      statusEl.innerHTML = message;
    }

    function escapeHtml(value) {
      return value.replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }[char]));
    }

    function renderSettings() {
      const notify = settings.notify_enabled ? settings.notify_service || "-" : "disabled";
      const collection = settings.collection_sensor_entity || "not configured";
      const diagnostics = settings._diagnostics || {};
      summaryEl.innerHTML = `
        <div>Sensor: <code>${settings.entity_id}</code></div>
        <div>RTSP: <code>${settings.rtsp_url ? "configured" : "missing"}</code></div>
        <div>Options file: <code>${diagnostics.options_file ? "loaded" : "missing"}</code></div>
        <div>Collection sensor: <code>${collection}</code></div>
        <div>Schedule: <code>${settings.monitor_days.join(",") || "all"} ${settings.active_time_start}-${settings.active_time_end}</code></div>
        <div>Scan interval: <code>${settings.scan_interval}s</code></div>
        <div>RTSP warmup: <code>${settings.rtsp_warmup_seconds}s</code></div>
        <div>Notifications: <code>${notify}</code></div>
      `;
      draw();
    }

    async function fetchJsonPayload(url) {
      const response = await fetch(url);
      const text = await response.text();
      try {
        return JSON.parse(text);
      } catch (error) {
        const contentType = response.headers.get("Content-Type") || "unknown";
        const preview = text.slice(0, 500) || "<empty response>";
        throw new Error(`Invalid JSON from ${url}. HTTP ${response.status}. Content-Type: ${contentType}. Body: ${preview}`);
      }
    }

    function syncCanvas() {
      canvas.width = img.clientWidth;
      canvas.height = img.clientHeight;
      draw();
    }

    function imageToCanvasRect(r) {
      const sx = canvas.width / img.naturalWidth;
      const sy = canvas.height / img.naturalHeight;
      return { x: r.x * sx, y: r.y * sy, width: r.width * sx, height: r.height * sy };
    }

    function canvasToImageRect(r) {
      const sx = img.naturalWidth / canvas.width;
      const sy = img.naturalHeight / canvas.height;
      return {
        x: Math.round(r.x * sx),
        y: Math.round(r.y * sy),
        width: Math.round(r.width * sx),
        height: Math.round(r.height * sy)
      };
    }

    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (!settings || !settings.roi || !img.naturalWidth) return;
      const r = imageToCanvasRect(settings.roi);
      ctx.lineWidth = 3;
      ctx.strokeStyle = "#f5c542";
      ctx.fillStyle = "rgba(245, 197, 66, 0.18)";
      ctx.fillRect(r.x, r.y, r.width, r.height);
      ctx.strokeRect(r.x, r.y, r.width, r.height);
      setStatus(`ROI: <code>x=${settings.roi.x}</code> <code>y=${settings.roi.y}</code> <code>width=${settings.roi.width}</code> <code>height=${settings.roi.height}</code>`);
    }

    function pointerPosition(event) {
      const rect = canvas.getBoundingClientRect();
      return {
        x: Math.max(0, Math.min(canvas.width, event.clientX - rect.left)),
        y: Math.max(0, Math.min(canvas.height, event.clientY - rect.top))
      };
    }

    canvas.addEventListener("pointerdown", (event) => {
      drawing = true;
      start = pointerPosition(event);
      canvas.setPointerCapture(event.pointerId);
    });

    canvas.addEventListener("pointermove", (event) => {
      if (!drawing || !settings) return;
      const end = pointerPosition(event);
      const rect = {
        x: Math.min(start.x, end.x),
        y: Math.min(start.y, end.y),
        width: Math.abs(end.x - start.x),
        height: Math.abs(end.y - start.y)
      };
      settings.roi = canvasToImageRect(rect);
      draw();
    });

    canvas.addEventListener("pointerup", (event) => {
      drawing = false;
      canvas.releasePointerCapture(event.pointerId);
    });

    async function loadSettings() {
      const response = await fetch("api/settings");
      settings = await response.json();
      renderSettings();
    }

    async function refreshSnapshot() {
      const requestId = ++snapshotRequestId;
      refreshButton.disabled = true;
      debugButton.disabled = true;
      setStatus("Loading snapshot...");
      try {
        const result = await fetchJsonPayload(`api/snapshot?t=${Date.now()}`);
        if (requestId !== snapshotRequestId) return;
        lastSnapshotError = result.error || "";
        if (result.ok) {
          img.src = `data:${result.content_type};base64,${result.image}`;
        } else {
          setStatus(`Snapshot unavailable: <code>${escapeHtml(result.error)}</code>`);
        }
      } catch (error) {
        if (requestId === snapshotRequestId) {
          lastSnapshotError = error.message;
          setStatus(`Snapshot unavailable: <code>${escapeHtml(error.message)}</code>`);
        }
      } finally {
        if (requestId === snapshotRequestId) {
          refreshButton.disabled = false;
          debugButton.disabled = false;
        }
      }
    }

    async function saveSettings() {
      const response = await fetch("api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({roi: settings.roi})
      });
      const result = await response.json();
      settings = result.settings;
      renderSettings();
      setStatus("ROI saved.");
      refreshSnapshot();
    }

    async function testNotification() {
      const response = await fetch("api/test-notification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}"
      });
      if (!response.ok) {
        setStatus("Test notification failed. Check notify service and logs.");
        return;
      }
      setStatus("Test notification sent.");
    }

    img.addEventListener("load", syncCanvas);
    img.addEventListener("error", () => {
      if (lastSnapshotError) {
        setStatus(`Snapshot unavailable: <code>${escapeHtml(lastSnapshotError)}</code>`);
      }
    });
    window.addEventListener("resize", syncCanvas);
    refreshButton.addEventListener("click", refreshSnapshot);
    debugButton.addEventListener("click", async () => {
      const requestId = ++snapshotRequestId;
      refreshButton.disabled = true;
      debugButton.disabled = true;
      setStatus("Loading debug snapshot...");
      try {
        const result = await fetchJsonPayload(`api/debug-snapshot?t=${Date.now()}`);
        if (requestId !== snapshotRequestId) return;
        lastSnapshotError = result.error || "";
        if (result.ok) {
          img.src = `data:${result.content_type};base64,${result.image}`;
        } else {
          setStatus(`Debug snapshot unavailable: <code>${escapeHtml(result.error)}</code>`);
        }
      } catch (error) {
        if (requestId === snapshotRequestId) {
          lastSnapshotError = error.message;
          setStatus(`Debug snapshot unavailable: <code>${escapeHtml(error.message)}</code>`);
        }
      } finally {
        if (requestId === snapshotRequestId) {
          refreshButton.disabled = false;
          debugButton.disabled = false;
        }
      }
    });
    document.getElementById("save").addEventListener("click", saveSettings);
    document.getElementById("test_notification").addEventListener("click", testNotification);

    loadSettings().then(refreshSnapshot).catch((error) => setStatus(error.message));
  </script>
</body>
</html>"""


def start_web_ui() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", UI_PORT), WebUiHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log(f"Web UI listening on port {UI_PORT}")


def analyze_frame(
    frame: np.ndarray,
    settings: dict[str, Any],
    current_candidate: str,
    hits: int,
) -> tuple[str, str, str, int, dict[str, Any], dict[str, float], dict[str, Any], bool]:
    min_ratio = float(settings.get("min_color_ratio", 0.08))
    required_frames = max(1, int(settings.get("consecutive_frames", 1)))
    ratios = color_ratios(frame, settings)
    quality = roi_quality(frame, settings)
    collection = expected_collection(settings)
    candidate_color = detected_color(ratios, min_ratio)

    if candidate_color != NONE_STATE and candidate_color == current_candidate:
        hits += 1
    else:
        current_candidate = candidate_color
        hits = 1 if candidate_color != NONE_STATE else 0

    stable_color = candidate_color if hits >= required_frames else NONE_STATE
    scheduled = is_scheduled_now(settings)
    verification_active = scheduled and collection["verification_active"]
    unreliable = verification_active and not bool(quality["reliable"])
    if unreliable:
        state = UNRELIABLE_STATE
    elif verification_active:
        state = stable_color
    else:
        state = NONE_STATE

    return state, candidate_color, current_candidate, hits, collection, ratios, quality, scheduled


def main() -> int:
    global LATEST_FRAME

    current_candidate = NONE_STATE
    hits = 0
    last_publish_signature: tuple[Any, ...] | None = None

    log("Starting Contarina bin detector")
    start_web_ui()

    while True:
        settings = load_settings()
        rtsp_url = settings["rtsp_url"].strip()
        interval = max(1, int(settings.get("scan_interval", 300)))

        if not rtsp_url:
            log("Waiting for RTSP URL configuration from Web UI")
            time.sleep(min(interval, 30))
            continue

        try:
            frame = capture_fresh_frame(rtsp_url)
        except Exception as error:
            log(f"Could not capture RTSP snapshot: {error}")
            time.sleep(min(interval, 60))
            continue


        with LATEST_FRAME_LOCK:
            LATEST_FRAME = frame.copy()

        state, candidate_color, current_candidate, hits, collection, ratios, quality, scheduled = analyze_frame(
            frame,
            settings,
            current_candidate,
            hits,
        )

        publish_signature = (
            state,
            collection["state"],
            collection["expected_state"],
            scheduled,
            quality["reason"],
        )
        if publish_signature != last_publish_signature:
            publish_state(settings, state, candidate_color, ratios, scheduled, collection, quality)
            last_publish_signature = publish_signature
            log(f"Published {settings['entity_id']}={state} ratios={ratios} scheduled={scheduled} collection={collection}")
        else:
            log(f"Scanned candidate={candidate_color} state={state} ratios={ratios} scheduled={scheduled} collection={collection}")

        try:
            manage_mobile_notification(settings, state, collection, scheduled, quality)
        except Exception as error:
            log(f"Could not manage mobile notification: {error}")

        time.sleep(interval)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        log(f"Fatal error: {error}")
        sys.exit(1)
