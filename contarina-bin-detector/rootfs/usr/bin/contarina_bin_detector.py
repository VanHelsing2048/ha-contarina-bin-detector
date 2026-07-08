#!/usr/bin/env python3
import json
import os
import sys
import time
from datetime import datetime, time as day_time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread
from typing import Any
from zoneinfo import ZoneInfo

import cv2
import numpy as np
import requests


SETTINGS_PATH = "/data/settings.json"
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
DARK_STATE = "non_verificabile_buio"
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
    "gray_hsv_lower": [0, 0, 45],
    "gray_hsv_upper": [179, 60, 210],
    "yellow_hsv_lower": [18, 60, 60],
    "yellow_hsv_upper": [38, 255, 255],
    "blue_hsv_lower": [90, 50, 40],
    "blue_hsv_upper": [130, 255, 255],
    "min_color_ratio": 0.08,
    "min_brightness": 35,
    "consecutive_frames": 3,
    "scan_interval": 10,
    "monitor_days": ["mon"],
    "active_time_start": "00:00",
    "active_time_end": "23:59",
}


def log(message: str) -> None:
    print(message, flush=True)


def load_settings() -> dict[str, Any]:
    settings = json.loads(json.dumps(DEFAULT_SETTINGS))
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as settings_file:
                saved = json.load(settings_file)
            settings.update(saved)
        except Exception as error:
            log(f"Ignoring invalid settings file: {error}")

    settings["roi"] = validate_roi(settings["roi"])
    for color in COLORS:
        settings[f"{color}_hsv_lower"] = validate_hsv(settings[f"{color}_hsv_lower"])
        settings[f"{color}_hsv_upper"] = validate_hsv(settings[f"{color}_hsv_upper"])
    settings["monitor_days"] = [
        day for day in settings.get("monitor_days", []) if str(day).lower() in WEEKDAYS
    ]
    settings["collection_mapping"] = validate_collection_mapping(settings.get("collection_mapping", {}))
    return settings


def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    merged = load_settings()
    merged.update(settings)
    merged["roi"] = validate_roi(merged["roi"])
    for color in COLORS:
        merged[f"{color}_hsv_lower"] = validate_hsv(merged[f"{color}_hsv_lower"])
        merged[f"{color}_hsv_upper"] = validate_hsv(merged[f"{color}_hsv_upper"])
    merged["min_color_ratio"] = max(0.0, min(1.0, float(merged["min_color_ratio"])))
    merged["min_brightness"] = max(0, min(255, int(merged["min_brightness"])))
    merged["consecutive_frames"] = max(1, int(merged["consecutive_frames"]))
    merged["scan_interval"] = max(1, int(merged["scan_interval"]))
    merged["monitor_days"] = [
        day for day in merged.get("monitor_days", []) if str(day).lower() in WEEKDAYS
    ]
    merged["collection_mapping"] = validate_collection_mapping(merged.get("collection_mapping", {}))

    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as settings_file:
        json.dump(merged, settings_file, indent=2)
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
    hue = max(0, min(179, int(value[0])))
    saturation = max(0, min(255, int(value[1])))
    brightness = max(0, min(255, int(value[2])))
    return [hue, saturation, brightness]


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


def roi_brightness(frame: np.ndarray, settings: dict[str, Any]) -> float:
    region = crop_roi(frame, settings["roi"])
    if region.size == 0:
        return 0.0
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    return float(np.mean(hsv[:, :, 2]))


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
    brightness: float,
    too_dark: bool,
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
            "brightness": round(brightness, 1),
            "too_dark": too_dark,
            "color_ratios": {color: round(ratio, 4) for color, ratio in ratios.items()},
            "min_color_ratio": float(settings["min_color_ratio"]),
            "min_brightness": int(settings["min_brightness"]),
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


def open_stream(rtsp_url: str) -> cv2.VideoCapture:
    capture = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return capture


def capture_snapshot(rtsp_url: str) -> bytes:
    if not rtsp_url:
        raise RuntimeError("Configure the RTSP URL first.")

    with LATEST_FRAME_LOCK:
        frame = None if LATEST_FRAME is None else LATEST_FRAME.copy()

    if frame is not None:
        return encode_snapshot(frame)

    capture = open_stream(rtsp_url)
    try:
        if not capture.isOpened():
            raise RuntimeError("RTSP stream is not open")

        frame = None
        for _ in range(5):
            ok, candidate = capture.read()
            if ok and candidate is not None:
                frame = candidate
                break

        if frame is None:
            raise RuntimeError("Could not read RTSP frame")

        return encode_snapshot(frame)
    finally:
        capture.release()


def encode_snapshot(frame: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise RuntimeError("Could not encode snapshot")
    return encoded.tobytes()


class WebUiHandler(BaseHTTPRequestHandler):
    server_version = "ContarinaWebUi/0.5"

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self.send_html(web_ui_html())
            return
        if self.path.startswith("/snapshot"):
            self.send_snapshot()
            return
        if self.path.startswith("/api/settings"):
            self.send_json(load_settings())
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path.startswith("/api/settings"):
            payload = self.read_json_body()
            saved = save_settings(payload)
            self.send_json({"ok": True, "settings": saved})
            log("Saved settings from Web UI")
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

    def send_snapshot(self) -> None:
        try:
            data = capture_snapshot(load_settings()["rtsp_url"])
        except Exception as error:
            self.send_error(HTTPStatus.BAD_GATEWAY, str(error))
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


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
    input { box-sizing: border-box; width: 100%; border: 1px solid #3d4d58; border-radius: 6px; padding: 9px 10px; background: #172027; color: #eef2f4; }
    button { border: 0; border-radius: 6px; padding: 9px 12px; background: #46a758; color: white; font-weight: 650; cursor: pointer; }
    button.secondary { background: #40515f; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    .days { display: flex; flex-wrap: wrap; gap: 8px; }
    .days label { display: flex; gap: 6px; align-items: center; }
    .days input { width: auto; }
    .stage { position: relative; display: inline-block; max-width: 100%; background: #050708; border: 1px solid #2d3a43; }
    img { display: block; max-width: 100%; height: auto; user-select: none; }
    canvas { position: absolute; inset: 0; width: 100%; height: 100%; cursor: crosshair; }
    .status { margin-top: 12px; color: #bcc8cf; font-size: 14px; }
    code { color: #d8e7ff; }
  </style>
</head>
<body>
  <main>
    <h1>Contarina Bin Detector</h1>
    <section>
      <h2>Camera and Sensor</h2>
      <div class="grid">
        <label>RTSP URL <input id="rtsp_url" autocomplete="off"></label>
        <label>Sensor entity <input id="entity_id"></label>
        <label>Name <input id="device_name"></label>
        <label>Timezone <input id="timezone"></label>
        <label>Collection sensor <input id="collection_sensor_entity" placeholder="sensor.raccolta_domani"></label>
      </div>
    </section>
    <section>
      <h2>Expected Collection Mapping</h2>
      <div class="grid">
        <label>Carta color <select id="map_Carta"></select></label>
        <label>VPL color <select id="map_VPL"></select></label>
        <label>Umido color <select id="map_Umido"></select></label>
        <label>Secco color <select id="map_Secco"></select></label>
      </div>
    </section>
    <section>
      <h2>Schedule</h2>
      <div class="grid">
        <label>Start time <input id="active_time_start" type="time"></label>
        <label>End time <input id="active_time_end" type="time"></label>
        <label>Scan interval seconds <input id="scan_interval" type="number" min="1"></label>
        <label>Stable frames <input id="consecutive_frames" type="number" min="1"></label>
        <label>Minimum brightness <input id="min_brightness" type="number" min="0" max="255"></label>
      </div>
      <div class="days" id="monitor_days"></div>
    </section>
    <section>
      <h2>Color Thresholds</h2>
      <div class="grid">
        <label>Minimum color ratio <input id="min_color_ratio" type="number" min="0" max="1" step="0.01"></label>
        <label>Gray lower HSV <input id="gray_hsv_lower"></label>
        <label>Gray upper HSV <input id="gray_hsv_upper"></label>
        <label>Yellow lower HSV <input id="yellow_hsv_lower"></label>
        <label>Yellow upper HSV <input id="yellow_hsv_upper"></label>
        <label>Blue lower HSV <input id="blue_hsv_lower"></label>
        <label>Blue upper HSV <input id="blue_hsv_upper"></label>
      </div>
    </section>
    <section>
      <div class="row">
        <h2>ROI</h2>
        <button class="secondary" id="refresh" type="button">Refresh frame</button>
        <button id="save" type="button">Save configuration</button>
      </div>
      <div class="stage">
        <img id="snapshot" alt="RTSP snapshot">
        <canvas id="overlay"></canvas>
      </div>
      <div class="status" id="status">Loading configuration...</div>
    </section>
  </main>
  <script>
    const fields = [
      "rtsp_url", "entity_id", "device_name", "timezone", "active_time_start",
      "active_time_end", "scan_interval", "consecutive_frames", "min_color_ratio",
      "min_brightness", "collection_sensor_entity",
      "gray_hsv_lower", "gray_hsv_upper", "yellow_hsv_lower", "yellow_hsv_upper",
      "blue_hsv_lower", "blue_hsv_upper"
    ];
    const weekdays = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
    const collectionLabels = ["Carta", "VPL", "Umido", "Secco"];
    const colorOptions = [
      ["gray", "grigio"],
      ["yellow", "giallo"],
      ["blue", "blu"]
    ];
    const img = document.getElementById("snapshot");
    const canvas = document.getElementById("overlay");
    const ctx = canvas.getContext("2d");
    const statusEl = document.getElementById("status");
    let settings = null;
    let drawing = false;
    let start = null;

    function setStatus(message) {
      statusEl.innerHTML = message;
    }

    function hsvToText(value) {
      return value.join(", ");
    }

    function textToHsv(value) {
      return value.split(",").map((part) => Number(part.trim()));
    }

    function buildDays() {
      const container = document.getElementById("monitor_days");
      container.innerHTML = "";
      weekdays.forEach((day) => {
        const label = document.createElement("label");
        label.innerHTML = `<input type="checkbox" value="${day}"> ${day}`;
        container.appendChild(label);
      });
    }

    function buildMappingSelects() {
      collectionLabels.forEach((label) => {
        const select = document.getElementById(`map_${label}`);
        select.innerHTML = "";
        colorOptions.forEach(([value, text]) => {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = text;
          select.appendChild(option);
        });
      });
    }

    function renderSettings() {
      fields.forEach((field) => {
        const input = document.getElementById(field);
        const value = settings[field];
        input.value = Array.isArray(value) ? hsvToText(value) : value;
      });
      document.querySelectorAll("#monitor_days input").forEach((input) => {
        input.checked = settings.monitor_days.includes(input.value);
      });
      collectionLabels.forEach((label) => {
        document.getElementById(`map_${label}`).value = settings.collection_mapping[label];
      });
      draw();
    }

    function collectSettings() {
      const next = {...settings};
      fields.forEach((field) => {
        const input = document.getElementById(field);
        if (field.endsWith("_hsv_lower") || field.endsWith("_hsv_upper")) {
          next[field] = textToHsv(input.value);
        } else if (["scan_interval", "consecutive_frames", "min_brightness"].includes(field)) {
          next[field] = Number(input.value);
        } else if (field === "min_color_ratio") {
          next[field] = Number(input.value);
        } else {
          next[field] = input.value;
        }
      });
      next.monitor_days = Array.from(document.querySelectorAll("#monitor_days input:checked")).map((input) => input.value);
      next.collection_mapping = {};
      collectionLabels.forEach((label) => {
        next.collection_mapping[label] = document.getElementById(`map_${label}`).value;
      });
      return next;
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
      setStatus("Loading snapshot...");
      img.src = `snapshot?t=${Date.now()}`;
    }

    async function saveSettings() {
      settings = collectSettings();
      const response = await fetch("api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings)
      });
      const result = await response.json();
      settings = result.settings;
      renderSettings();
      setStatus("Configuration saved.");
      refreshSnapshot();
    }

    img.addEventListener("load", syncCanvas);
    img.addEventListener("error", () => setStatus("Snapshot unavailable. Check the RTSP URL and save the configuration."));
    window.addEventListener("resize", syncCanvas);
    document.getElementById("refresh").addEventListener("click", refreshSnapshot);
    document.getElementById("save").addEventListener("click", saveSettings);

    buildDays();
    buildMappingSelects();
    loadSettings().then(refreshSnapshot).catch((error) => setStatus(error.message));
  </script>
</body>
</html>"""


def start_web_ui() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", UI_PORT), WebUiHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log(f"Web UI listening on port {UI_PORT}")


def main() -> int:
    global LATEST_FRAME

    current_candidate = NONE_STATE
    hits = 0
    last_publish_signature: tuple[Any, ...] | None = None
    current_rtsp_url = ""
    capture: cv2.VideoCapture | None = None

    log("Starting Contarina bin detector")
    start_web_ui()

    while True:
        settings = load_settings()
        rtsp_url = settings["rtsp_url"].strip()
        interval = max(1, int(settings.get("scan_interval", 10)))
        required_frames = max(1, int(settings.get("consecutive_frames", 3)))
        min_ratio = float(settings.get("min_color_ratio", 0.08))

        if not rtsp_url:
            log("Waiting for RTSP URL configuration from Web UI")
            time.sleep(interval)
            continue

        if capture is None or rtsp_url != current_rtsp_url:
            if capture is not None:
                capture.release()
            current_rtsp_url = rtsp_url
            capture = open_stream(rtsp_url)
            with LATEST_FRAME_LOCK:
                LATEST_FRAME = None

        if not capture.isOpened():
            log("RTSP stream is closed; reconnecting in 10 seconds")
            capture.release()
            capture = None
            time.sleep(10)
            continue

        ok, frame = capture.read()
        if not ok or frame is None:
            log("Could not read frame; reconnecting in 10 seconds")
            capture.release()
            capture = None
            time.sleep(10)
            continue

        with LATEST_FRAME_LOCK:
            LATEST_FRAME = frame.copy()

        ratios = color_ratios(frame, settings)
        brightness = roi_brightness(frame, settings)
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
        too_dark = verification_active and brightness < int(settings["min_brightness"])
        if too_dark:
            state = DARK_STATE
        elif verification_active:
            state = stable_color
        else:
            state = NONE_STATE

        publish_signature = (
            state,
            collection["state"],
            collection["expected_state"],
            scheduled,
            too_dark,
        )
        if publish_signature != last_publish_signature:
            publish_state(settings, state, candidate_color, ratios, scheduled, collection, brightness, too_dark)
            last_publish_signature = publish_signature
            log(f"Published {settings['entity_id']}={state} ratios={ratios} scheduled={scheduled} collection={collection}")
        else:
            log(f"Scanned candidate={candidate_color} state={state} ratios={ratios} scheduled={scheduled} collection={collection}")

        time.sleep(interval)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        log(f"Fatal error: {error}")
        sys.exit(1)
