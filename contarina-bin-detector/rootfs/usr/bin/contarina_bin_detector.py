#!/usr/bin/env python3
import json
import os
import sys
import time
from datetime import datetime, time as day_time
from typing import Any
from zoneinfo import ZoneInfo

import cv2
import numpy as np
import requests


OPTIONS_PATH = "/data/options.json"
CORE_API_BASE = "http://supervisor/core/api"
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
COLORS = ("gray", "yellow", "blue")
STATE_NAMES = {
    "gray": "grigio",
    "yellow": "giallo",
    "blue": "blu",
}
NONE_STATE = "nessun_bidone"


def log(message: str) -> None:
    print(message, flush=True)


def load_options() -> dict[str, Any]:
    with open(OPTIONS_PATH, "r", encoding="utf-8") as options_file:
        return json.load(options_file)


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


def main() -> int:
    options = load_options()
    rtsp_url = options["rtsp_url"]
    interval = max(1, int(options.get("scan_interval", 10)))
    required_frames = max(1, int(options.get("consecutive_frames", 3)))
    min_ratio = float(options.get("min_color_ratio", 0.08))
    current_candidate = NONE_STATE
    hits = 0
    last_state: str | None = None

    log("Starting Contarina bin detector")
    capture = open_stream(rtsp_url)

    while True:
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
