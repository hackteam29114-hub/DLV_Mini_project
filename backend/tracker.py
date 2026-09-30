"""
tracker.py
----------
Responsible for:
  * Maintaining per-track state across frames (position history)
  * Providing helper info used for direction detection and counting
    (previous center point, number of frames seen, last-seen timestamp)
  * Reporting how many tracks are currently "active" (seen recently)

Note: the actual frame-to-frame identity association (ByteTrack) is
performed inside detector.py via Ultralytics' built-in `model.track()`.
This module manages the *history* of those track IDs so that counter.py
can reason about line crossings using previous vs current position.
"""

import time
import logging

logger = logging.getLogger("vehicle_tracker")

# A track is considered "stale" (no longer active) if not seen for this long.
TRACK_TIMEOUT_SECONDS = 2.0


class TrackState:
    __slots__ = ("track_id", "class_name", "prev_center", "current_center", "last_seen", "frames_seen")

    def __init__(self, track_id, class_name, center):
        self.track_id = track_id
        self.class_name = class_name
        self.prev_center = None
        self.current_center = center
        self.last_seen = time.time()
        self.frames_seen = 1


class TrackManager:
    """Keeps a dictionary of TrackState objects keyed by track_id."""

    def __init__(self):
        self.tracks = {}

    def update(self, detections):
        """
        Update internal state with the latest frame's detections.
        `detections` is the list produced by VehicleDetector.detect_and_track().

        Returns the same list of detections, enriched with a "prev_center" key
        so counter.py can compute line-crossing direction.
        """
        now = time.time()
        seen_ids = set()

        for det in detections:
            tid = det["track_id"]
            seen_ids.add(tid)
            center = det["center"]

            if tid in self.tracks:
                state = self.tracks[tid]
                state.prev_center = state.current_center
                state.current_center = center
                state.last_seen = now
                state.frames_seen += 1
            else:
                state = TrackState(tid, det["class_name"], center)
                self.tracks[tid] = state

            det["prev_center"] = self.tracks[tid].prev_center

        self._cleanup_stale(now)
        return detections

    def _cleanup_stale(self, now):
        stale_ids = [
            tid for tid, state in self.tracks.items()
            if now - state.last_seen > TRACK_TIMEOUT_SECONDS
        ]
        for tid in stale_ids:
            del self.tracks[tid]

    def active_track_count(self):
        return len(self.tracks)

    def reset(self):
        self.tracks.clear()
