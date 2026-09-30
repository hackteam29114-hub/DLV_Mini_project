"""
config.py
---------
Centralized configuration for the Vehicle Detection & Counting System.
Change values here to tune the whole application without touching
any other module.
"""

import os

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

MODELS_DIR = os.path.join(BASE_DIR, "models")
UPLOADS_DIR = os.path.join(PROJECT_ROOT, "uploads")
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "outputs")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
DB_PATH = os.path.join(OUTPUTS_DIR, "detections.db")

for _d in (MODELS_DIR, UPLOADS_DIR, OUTPUTS_DIR, LOGS_DIR):
    os.makedirs(_d, exist_ok=True)

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------
# Pretrained model used by default. Ultralytics will automatically download
# this file on first run if it is not already present in MODELS_DIR / cwd.
# To use your own trained model, drop a .pt file at backend/models/custom_model.pt
# and set MODEL_PATH below (or leave USE_CUSTOM_MODEL_IF_PRESENT = True).
DEFAULT_MODEL_NAME = "yolov8n.pt"
MODEL_PATH = os.path.join(MODELS_DIR, DEFAULT_MODEL_NAME)
CUSTOM_MODEL_PATH = os.path.join(MODELS_DIR, "custom_model.pt")
USE_CUSTOM_MODEL_IF_PRESENT = True

# COCO class IDs for the vehicle classes we care about.
# (Standard COCO dataset indices used by Ultralytics YOLO pretrained models.)
VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

# Add more COCO classes here later if desired, e.g. 1: "bicycle"

# ---------------------------------------------------------------------------
# Detection / tracking configuration
# ---------------------------------------------------------------------------
DEFAULT_CONFIDENCE_THRESHOLD = 0.40
MIN_CONFIDENCE_THRESHOLD = 0.10
MAX_CONFIDENCE_THRESHOLD = 1.00

# Tracker type supported by Ultralytics: "bytetrack.yaml" or "botsort.yaml"
TRACKER_CONFIG = "bytetrack.yaml"

# ---------------------------------------------------------------------------
# Counting line configuration
# ---------------------------------------------------------------------------
DEFAULT_LINE_POSITION_PCT = 0.50  # 50% of frame height
DEFAULT_COUNTING_DIRECTION = "both"  # "down", "up", "both"

# ---------------------------------------------------------------------------
# Video / performance configuration
# ---------------------------------------------------------------------------
PROCESSING_WIDTH = 640
PROCESSING_HEIGHT = 480
JPEG_QUALITY = 80  # for MJPEG streaming
TARGET_STREAM_FPS = 25  # cap to avoid overloading the browser/socket
RECENT_DETECTIONS_LIMIT = 50

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}

# ---------------------------------------------------------------------------
# Server configuration
# ---------------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 8000
