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


OPTIONS_PATH = "/data/options.json"
ROI_OVERRIDE_PATH = "/data/roi.json"
CORE_API_BASE = "http://supervisor/core/api"
ROI_UI_PORT = 8099
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
COLORS = ("gray", "yellow", "blue")
STATE_NAMES = {
    "gray": "grigio",
    "yellow": "giallo",
    "blue": "blu",
}
NONE_STATE = "nessun_bidone"
LATEST_FRAME: np.ndarray | None = None
LATEST_FRAME_LOCK = Lock()


def log(message: str) -> None:
    print(message, flush=True)


def load_options() -> dict[str, Any]:
    with open(OPTIONS_PATH, "r", encoding="utf-8") as options_file:
        options = json.load(options_file)

    override = load_roi_override()
    if override:
        options["roi"] = override
    return options


def load_roi_override() -> dict[str, int] | None:
    if not os.path.exists(ROI_OVERRIDE_PATH):
        return None
    try:
        with open(ROI_OVERRIDE_PATH, "r", encoding="utf-8") as roi_file:
            roi = json.load(roi_file)
        return validate_roi(roi)
    except Exception as error:
        log(f"Ignoring invalid ROI override: {error}")
        return None


def save_roi_override(roi: dict[str, Any]) -> dict[str, int]:
    validated = validate_roi(roi)
    os.makedirs(os.path.dirname(ROI_OVERRIDE_PATH), exist_ok=True)
    with open(ROI_OVERRIDE_PATH, "w", encoding="utf-8") as roi_file:
        json.dump(validated, roi_file, indent=2)
        roi_file.write("\n")
    return validated


def validate_roi(roi: dict[str, Any]) -> dict[str, int]:
    validated = {
        "x": max(0, int(roi["x"])),
        "y": max(0, int(roi["y"])),
        "width": max(1, int(roi["width"])),
        "height": max(1, int(roi["height"])),
    }
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


def is_scheduled_now(options: dict[str, Any]) -> bool:
    timezone = ZoneInfo(options.get("timezone", "Europe/Rome"))
    now = datetime.now(timezone)
    monitor_days = [day.lower() for day in options.get("monitor_days", [])]
    day_matches = not monitor_days or WEEKDAYS[now.weekday()] in monitor_days
    time_matches = is_time_in_window(
        now,
        options.get("active_time_start", "00:00"),
        options.get("active_time_end", "23:59"),
    )
    return day_matches and time_matches


def crop_roi(frame: np.ndarray, roi: dict[str, int]) -> np.ndarray:
    height, width = frame.shape[:2]
    x1 = max(0, min(width, int(roi["x"])))
    y1 = max(0, min(height, int(roi["y"])))
    x2 = max(x1, min(width, x1 + int(roi["width"])))
    y2 = max(y1, min(height, y1 + int(roi["height"])))
    return frame[y1:y2, x1:x2]


def color_ratios(frame: np.ndarray, options: dict[str, Any]) -> dict[str, float]:
    region = crop_roi(frame, options["roi"])
    if region.size == 0:
        return {color: 0.0 for color in COLORS}

    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    ratios = {}
    for color, hsv_range in configured_color_ranges(options).items():
        lower = np.array(hsv_range["lower"], dtype=np.uint8)
        upper = np.array(hsv_range["upper"], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)
        ratios[color] = float(cv2.countNonZero(mask)) / float(mask.size)
    return ratios


def configured_color_ranges(options: dict[str, Any]) -> dict[str, dict[str, list[int]]]:
    return {
        color: {
            "lower": options[f"{color}_hsv_lower"],
            "upper": options[f"{color}_hsv_upper"],
        }
        for color in COLORS
    }


def detected_color(ratios: dict[str, float], min_ratio: float) -> str:
    color = max(ratios, key=ratios.get)
    if ratios[color] >= min_ratio:
        return STATE_NAMES[color]
    return NONE_STATE


def publish_state(
    options: dict[str, Any],
    state: str,
    candidate_color: str,
    ratios: dict[str, float],
    scheduled: bool,
) -> None:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise RuntimeError("SUPERVISOR_TOKEN is not available; enable homeassistant_api in config.yaml.")

    entity_id = options["entity_id"]
    payload = {
        "state": state,
        "attributes": {
            "friendly_name": options.get("device_name", "Bidone Contarina"),
            "detected": state != NONE_STATE,
            "candidate_color": candidate_color,
            "scheduled_now": scheduled,
            "color_ratios": {color: round(ratio, 4) for color, ratio in ratios.items()},
            "min_color_ratio": float(options["min_color_ratio"]),
            "roi": options["roi"],
            "color_ranges": configured_color_ranges(options),
            "last_scan": datetime.now(ZoneInfo(options.get("timezone", "Europe/Rome"))).isoformat(),
        },
    }
    response = requests.post(
        f"{CORE_API_BASE}/states/{entity_id}",
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


class RoiUiHandler(BaseHTTPRequestHandler):
    server_version = "ContarinaRoiUi/0.3"

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self.send_html(roi_ui_html())
            return
        if self.path.startswith("/snapshot"):
            self.send_snapshot()
            return
        if self.path.startswith("/api/config"):
            self.send_json({"roi": load_options()["roi"]})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path.startswith("/api/roi"):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            roi = json.loads(body.decode("utf-8"))
            saved = save_roi_override(roi)
            self.send_json({"ok": True, "roi": saved})
            log(f"Saved ROI override: {saved}")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        log(f"ROI UI: {format % args}")

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
            data = capture_snapshot(load_options()["rtsp_url"])
        except Exception as error:
            self.send_error(HTTPStatus.BAD_GATEWAY, str(error))
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def roi_ui_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Contarina ROI</title>
  <style>
    :root { color-scheme: light dark; font-family: system-ui, sans-serif; }
    body { margin: 0; background: #101418; color: #eef2f4; }
    main { max-width: 1180px; margin: 0 auto; padding: 16px; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
    h1 { font-size: 20px; margin: 0; font-weight: 650; }
    button { border: 0; border-radius: 6px; padding: 9px 12px; background: #46a758; color: white; font-weight: 650; cursor: pointer; }
    button.secondary { background: #40515f; }
    .tools { display: flex; gap: 8px; flex-wrap: wrap; }
    .stage { position: relative; display: inline-block; max-width: 100%; background: #050708; border: 1px solid #2d3a43; }
    img { display: block; max-width: 100%; height: auto; user-select: none; }
    canvas { position: absolute; inset: 0; width: 100%; height: 100%; cursor: crosshair; }
    .status { margin-top: 12px; color: #bcc8cf; font-size: 14px; }
    code { color: #d8e7ff; }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Contarina ROI</h1>
      <div class="tools">
        <button class="secondary" id="refresh">Refresh frame</button>
        <button id="save">Save ROI</button>
      </div>
    </header>
    <div class="stage">
      <img id="snapshot" alt="RTSP snapshot">
      <canvas id="overlay"></canvas>
    </div>
    <div class="status" id="status">Loading snapshot...</div>
  </main>
  <script>
    const img = document.getElementById("snapshot");
    const canvas = document.getElementById("overlay");
    const ctx = canvas.getContext("2d");
    const statusEl = document.getElementById("status");
    let roi = null;
    let drawing = false;
    let start = null;

    function setStatus(message) {
      statusEl.innerHTML = message;
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
      if (!roi || !img.naturalWidth) return;
      const r = imageToCanvasRect(roi);
      ctx.lineWidth = 3;
      ctx.strokeStyle = "#f5c542";
      ctx.fillStyle = "rgba(245, 197, 66, 0.18)";
      ctx.fillRect(r.x, r.y, r.width, r.height);
      ctx.strokeRect(r.x, r.y, r.width, r.height);
      setStatus(`ROI: <code>x=${roi.x}</code> <code>y=${roi.y}</code> <code>width=${roi.width}</code> <code>height=${roi.height}</code>`);
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
      if (!drawing) return;
      const end = pointerPosition(event);
      const rect = {
        x: Math.min(start.x, end.x),
        y: Math.min(start.y, end.y),
        width: Math.abs(end.x - start.x),
        height: Math.abs(end.y - start.y)
      };
      roi = canvasToImageRect(rect);
      draw();
    });

    canvas.addEventListener("pointerup", (event) => {
      drawing = false;
      canvas.releasePointerCapture(event.pointerId);
    });

    async function loadConfig() {
      const response = await fetch("api/config");
      const config = await response.json();
      roi = config.roi;
    }

    async function refreshSnapshot() {
      setStatus("Loading snapshot...");
      img.src = `snapshot?t=${Date.now()}`;
    }

    img.addEventListener("load", syncCanvas);
    window.addEventListener("resize", syncCanvas);

    document.getElementById("refresh").addEventListener("click", refreshSnapshot);
    document.getElementById("save").addEventListener("click", async () => {
      if (!roi || roi.width < 1 || roi.height < 1) {
        setStatus("Draw a rectangle before saving.");
        return;
      }
      const response = await fetch("api/roi", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(roi)
      });
      const result = await response.json();
      roi = result.roi;
      draw();
      setStatus(`Saved ROI: <code>x=${roi.x}</code> <code>y=${roi.y}</code> <code>width=${roi.width}</code> <code>height=${roi.height}</code>`);
    });

    loadConfig().then(refreshSnapshot).catch((error) => setStatus(error.message));
  </script>
</body>
</html>"""


def start_roi_ui() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", ROI_UI_PORT), RoiUiHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log(f"ROI UI listening on port {ROI_UI_PORT}")


def main() -> int:
    global LATEST_FRAME

    options = load_options()
    rtsp_url = options["rtsp_url"]
    interval = max(1, int(options.get("scan_interval", 10)))
    required_frames = max(1, int(options.get("consecutive_frames", 3)))
    min_ratio = float(options.get("min_color_ratio", 0.08))
    current_candidate = NONE_STATE
    hits = 0
    last_state: str | None = None

    log("Starting Contarina bin detector")
    start_roi_ui()
    capture = open_stream(rtsp_url)

    while True:
        options = load_options()
        interval = max(1, int(options.get("scan_interval", 10)))
        required_frames = max(1, int(options.get("consecutive_frames", 3)))
        min_ratio = float(options.get("min_color_ratio", 0.08))

        if not capture.isOpened():
            log("RTSP stream is closed; reconnecting in 10 seconds")
            capture.release()
            time.sleep(10)
            capture = open_stream(rtsp_url)
            continue

        ok, frame = capture.read()
        if not ok or frame is None:
            log("Could not read frame; reconnecting in 10 seconds")
            capture.release()
            time.sleep(10)
            capture = open_stream(rtsp_url)
            continue

        with LATEST_FRAME_LOCK:
            LATEST_FRAME = frame.copy()

        ratios = color_ratios(frame, options)
        candidate_color = detected_color(ratios, min_ratio)
        if candidate_color != NONE_STATE and candidate_color == current_candidate:
            hits += 1
        else:
            current_candidate = candidate_color
            hits = 1 if candidate_color != NONE_STATE else 0

        stable_color = candidate_color if hits >= required_frames else NONE_STATE
        scheduled = is_scheduled_now(options)
        state = stable_color if scheduled else NONE_STATE

        if state != last_state:
            publish_state(options, state, candidate_color, ratios, scheduled)
            last_state = state
            log(f"Published {options['entity_id']}={state} ratios={ratios} scheduled={scheduled}")
        else:
            log(f"Scanned candidate={candidate_color} state={state} ratios={ratios} scheduled={scheduled}")

        time.sleep(interval)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        log(f"Fatal error: {error}")
        sys.exit(1)
