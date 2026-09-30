"""
counter.py
----------
Responsible for:
  * Holding the configurable counting line (position + direction mode)
  * Detecting when a tracked vehicle's center point crosses the line
  * Preventing duplicate counts (each track_id is only ever counted once)
  * Maintaining per-class and total counts
  * Recording a log of "recent detections" for the dashboard table / CSV export
"""

import csv
import io
import logging
import time
from collections import deque

import config

logger = logging.getLogger("vehicle_counter")


class VehicleCounter:
    def __init__(self):
        self.line_position_pct = config.DEFAULT_LINE_POSITION_PCT
        self.direction_mode = config.DEFAULT_COUNTING_DIRECTION  # "down", "up", "both"

        self.counted_ids = set()  # track_ids that have already been counted
        self.counts = {name: 0 for name in config.VEHICLE_CLASSES.values()}
        self.total = 0

        # Each entry: dict(time, track_id, vehicle_type, confidence, direction)
        self.recent_detections = deque(maxlen=config.RECENT_DETECTIONS_LIMIT)
        self.full_history = []  # kept for CSV export (session lifetime)

        # Traffic-flow-over-time buckets, e.g. {"10:00": 5, "10:05": 12, ...}
        self.flow_series = deque(maxlen=200)
        self._last_flow_bucket_time = 0
        self._flow_bucket_seconds = 5

    # ------------------------------------------------------------------
    # Configuration setters (called from the /start or config endpoints)
    # ------------------------------------------------------------------
    def set_line_position(self, pct: float):
        self.line_position_pct = max(0.0, min(1.0, pct))

    def set_direction_mode(self, mode: str):
        if mode in ("down", "up", "both"):
            self.direction_mode = mode

    def line_y(self, frame_height: int) -> int:
        return int(frame_height * self.line_position_pct)

    # ------------------------------------------------------------------
    # Core counting logic
    # ------------------------------------------------------------------
    def process_detections(self, detections, frame_height: int):
        """
        For every detection this frame, check whether its track crossed the
        counting line since the previous frame. Uses the center-point of the
        bounding box, comparing previous vs current Y position against the
        line's Y coordinate.
        """
        line_y = self.line_y(frame_height)

        for det in detections:
            track_id = det["track_id"]
            prev_center = det.get("prev_center")
            current_center = det["center"]

            if prev_center is None:
                continue  # first time we've seen this track; nothing to compare yet

            if track_id in self.counted_ids:
                continue  # already counted -> never count the same ID twice

            prev_y = prev_center[1]
            curr_y = current_center[1]

            crossed_down = prev_y < line_y <= curr_y
            crossed_up = prev_y > line_y >= curr_y

            direction = None
            if crossed_down and self.direction_mode in ("down", "both"):
                direction = "Down"
            elif crossed_up and self.direction_mode in ("up", "both"):
                direction = "Up"

            if direction is not None:
                self._register_count(det, direction)

        self._update_flow_series()

    def _register_count(self, det, direction):
        track_id = det["track_id"]
        class_name = det["class_name"]

        self.counted_ids.add(track_id)
        self.counts[class_name] = self.counts.get(class_name, 0) + 1
        self.total += 1

        entry = {
            "time": time.strftime("%H:%M:%S"),
            "track_id": track_id,
            "vehicle_type": class_name,
            "confidence": round(det["confidence"] * 100, 1),
            "direction": direction,
        }
        self.recent_detections.append(entry)
        self.full_history.append(entry)
        logger.info(f"Counted vehicle: {entry}")

    def _update_flow_series(self):
        now = time.time()
        if now - self._last_flow_bucket_time >= self._flow_bucket_seconds:
            self._last_flow_bucket_time = now
            label = time.strftime("%H:%M:%S")
            self.flow_series.append({"time": label, "count": self.total})

    # ------------------------------------------------------------------
    # Reset / export
    # ------------------------------------------------------------------
    def reset(self):
        self.counted_ids.clear()
        self.counts = {name: 0 for name in config.VEHICLE_CLASSES.values()}
        self.total = 0
        self.recent_detections.clear()
        self.full_history.clear()
        self.flow_series.clear()
        self._last_flow_bucket_time = 0
        logger.info("Counter state reset.")

    def get_stats(self):
        return {
            "total": self.total,
            "counts": self.counts,
            "recent_detections": list(self.recent_detections),
            "flow_series": list(self.flow_series),
        }

    def export_csv(self) -> str:
        """Returns CSV text of the full session history."""
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["timestamp", "tracking_id", "vehicle_type", "confidence", "direction"])
        for entry in self.full_history:
            writer.writerow(
                [entry["time"], entry["track_id"], entry["vehicle_type"], entry["confidence"], entry["direction"]]
            )
        return buffer.getvalue()
