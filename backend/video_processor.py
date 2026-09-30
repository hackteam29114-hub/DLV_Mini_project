"""
video_processor.py
-------------------
Responsible for:
  * Reading frames from a video file or webcam (OpenCV VideoCapture)
  * Running detection (detector.py) + track-state updates (tracker.py)
  * Running counting logic (counter.py)
  * Drawing all annotations (bounding boxes, labels, counting line, IDs)
  * Calculating real-time FPS
  * Encoding frames as JPEG for MJPEG / WebSocket streaming

This is the "engine" that main.py drives via start/stop calls.
"""

import logging
import platform
import threading
import time

import cv2

import config
from counter import VehicleCounter
from detector import VehicleDetector
from tracker import TrackManager

logger = logging.getLogger("video_processor")

# Distinct BGR colors per vehicle class for clearer visualization
CLASS_COLORS = {
    "car": (0, 200, 255),        # amber
    "motorcycle": (255, 100, 0),  # blue-ish
    "bus": (0, 220, 0),          # green
    "truck": (0, 0, 255),        # red
}


class VideoProcessor:
    """
    Encapsulates the full real-time processing pipeline for either a webcam
    index or a video file path. Runs in a background thread so the FastAPI
    event loop stays responsive.
    """

    def __init__(self):
        self.detector = VehicleDetector()
        self.tracker = TrackManager()
        self.counter = VehicleCounter()

        self.cap = None
        self.source = None  # 0 (webcam) or a file path
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

        self.latest_frame_jpeg = None  # bytes, for MJPEG/WebSocket consumers
        self.confidence_threshold = config.DEFAULT_CONFIDENCE_THRESHOLD

        self.fps = 0.0
        self._frame_times = []
        self.device = self.detector.device
        self.error_message = None
        self.status = "stopped"  # "stopped" | "running" | "error"

    # ------------------------------------------------------------------
    # Public control API (called from main.py)
    # ------------------------------------------------------------------
    def configure(self, confidence=None, line_position=None, direction=None):
        if confidence is not None:
            self.confidence_threshold = max(
                config.MIN_CONFIDENCE_THRESHOLD, min(config.MAX_CONFIDENCE_THRESHOLD, confidence)
            )
        if line_position is not None:
            self.counter.set_line_position(line_position)
        if direction is not None:
            self.counter.set_direction_mode(direction)

    def start(self, source):
        """
        source: 0 (int) for webcam, or a string file path for an uploaded video.
        """
        with self.lock:
            if self.running:
                self.stop()

            self.error_message = None
            self.source = source
            self.cap = self._open_capture(source)

            if not self.cap.isOpened():
                self.error_message = (
                    "Unable to access webcam. Please check camera permissions, "
                    "make sure no other application (Zoom, Teams, etc.) is using it, "
                    "and that a webcam is actually connected."
                    if source == 0
                    else "Unable to open the uploaded video. The file may be corrupted or in an unsupported format."
                )
                self.status = "error"
                logger.error(self.error_message)
                return False, self.error_message

            self.running = True
            self.status = "running"
            self.tracker.reset()
            self._frame_times = []
            self.thread = threading.Thread(target=self._process_loop, daemon=True)
            self.thread.start()
            logger.info(f"Started processing source={source}")
            return True, None

    @staticmethod
    def _open_capture(source):
        """
        Opens an OpenCV VideoCapture, choosing a backend that avoids common
        Windows webcam issues. On Windows, the default backend (MSMF/obsensor)
        frequently fails with 'Camera index out of range' even when a webcam
        is present and working, so DirectShow (CAP_DSHOW) is tried first for
        integer (webcam) sources. File sources always use the default backend.
        """
        if isinstance(source, int) and platform.system() == "Windows":
            cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
            if cap.isOpened():
                return cap
            cap.release()
            # Fall back to the default backend in case DirectShow isn't available
            return cv2.VideoCapture(source)
        return cv2.VideoCapture(source)

    def stop(self):
        with self.lock:
            self.running = False
        if self.thread is not None:
            self.thread.join(timeout=2.0)
            self.thread = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.status = "stopped"
        logger.info("Processing stopped.")

    def reset_counts(self):
        self.counter.reset()
        self.tracker.reset()

    # ------------------------------------------------------------------
    # Frame processing loop (runs in background thread)
    # ------------------------------------------------------------------
    def _process_loop(self):
        target_frame_time = 1.0 / config.TARGET_STREAM_FPS

        while self.running:
            loop_start = time.time()

            if self.cap is None:
                break
            ret, frame = self.cap.read()

            if not ret:
                # End of file (for uploaded videos) or webcam read failure
                if isinstance(self.source, str):
                    logger.info("Reached end of uploaded video.")
                else:
                    self.error_message = "Webcam disconnected or unavailable."
                    logger.error(self.error_message)
                self.status = "stopped"
                self.running = False
                break

            try:
                processed = self._process_frame(frame)
                ok, buf = cv2.imencode(
                    ".jpg", processed, [int(cv2.IMWRITE_JPEG_QUALITY), config.JPEG_QUALITY]
                )
                if ok:
                    with self.lock:
                        self.latest_frame_jpeg = buf.tobytes()
            except Exception as exc:
                logger.exception(f"Error while processing frame: {exc}")
                self.error_message = f"Processing error: {exc}"

            # FPS calculation (rolling average over last 30 frames)
            now = time.time()
            self._frame_times.append(now)
            if len(self._frame_times) > 30:
                self._frame_times.pop(0)
            if len(self._frame_times) >= 2:
                span = self._frame_times[-1] - self._frame_times[0]
                if span > 0:
                    self.fps = (len(self._frame_times) - 1) / span

            elapsed = time.time() - loop_start
            sleep_time = target_frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _process_frame(self, frame):
        frame = cv2.resize(frame, (config.PROCESSING_WIDTH, config.PROCESSING_HEIGHT))
        height, width = frame.shape[:2]

        detections = self.detector.detect_and_track(frame, self.confidence_threshold)
        detections = self.tracker.update(detections)
        self.counter.process_detections(detections, height)

        self._draw_annotations(frame, detections, width, height)
        return frame

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------
    def _draw_annotations(self, frame, detections, width, height):
        line_y = self.counter.line_y(height)
        cv2.line(frame, (0, line_y), (width, line_y), (0, 255, 255), 2)
        cv2.putText(
            frame, "COUNTING LINE", (10, max(20, line_y - 10)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA,
        )

        for det in detections:
            x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
            color = CLASS_COLORS.get(det["class_name"], (255, 255, 255))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            label = f'{det["class_name"].upper()} ID:{det["track_id"]} {det["confidence"]*100:.0f}%'
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
            cv2.putText(
                frame, label, (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA,
            )

            cx, cy = int(det["center"][0]), int(det["center"][1])
            cv2.circle(frame, (cx, cy), 3, color, -1)

        overlay_text = f"Device: {self.device.upper()}  FPS: {self.fps:.1f}  Active: {self.tracker.active_track_count()}"
        cv2.putText(
            frame, overlay_text, (10, height - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA,
        )

    # ------------------------------------------------------------------
    # Data accessors used by main.py
    # ------------------------------------------------------------------
    def get_latest_jpeg(self):
        with self.lock:
            return self.latest_frame_jpeg

    def get_stats(self):
        stats = self.counter.get_stats()
        return {
            "total": stats["total"],
            "cars": stats["counts"].get("car", 0),
            "motorcycles": stats["counts"].get("motorcycle", 0),
            "buses": stats["counts"].get("bus", 0),
            "trucks": stats["counts"].get("truck", 0),
            "active_tracks": self.tracker.active_track_count(),
            "fps": round(self.fps, 1),
            "status": self.status,
            "device": self.device,
            "confidence_threshold": self.confidence_threshold,
            "line_position": self.counter.line_position_pct,
            "direction_mode": self.counter.direction_mode,
            "recent_detections": stats["recent_detections"],
            "flow_series": stats["flow_series"],
            "error": self.error_message,
        }
