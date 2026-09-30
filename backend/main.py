"""
main.py
-------
Responsible for:
  * FastAPI application setup
  * REST API endpoints (upload, start, stop, reset, stats, export, video)
  * MJPEG streaming endpoint for the processed video
  * Serving the static frontend (HTML/CSS/JS)
  * Application lifecycle (startup / shutdown)

Run with:
    python -m uvicorn backend.main:app --reload
from the project root, then open http://127.0.0.1:8000
"""

import logging
import os
import sqlite3
import sys
import time
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Allow running both as `python -m uvicorn backend.main:app` (from project root)
# and directly (e.g. `python main.py` from inside backend/).
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from video_processor import VideoProcessor

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
os.makedirs(config.LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(config.LOGS_DIR, "app.log")),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("main")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="AI Vehicle Detection & Counting API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global processor instance. Created lazily on first /start so that a failed
# model load doesn't crash the whole server at import time.
processor: VideoProcessor = None
current_video_path: str = None


def get_processor() -> VideoProcessor:
    global processor
    if processor is None:
        try:
            processor = VideoProcessor()
        except Exception as exc:
            logger.exception("Failed to initialize VideoProcessor")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load YOLO model. Make sure ultralytics and its "
                       f"dependencies are installed correctly. Error: {exc}",
            )
    return processor


# ---------------------------------------------------------------------------
# SQLite storage
# ---------------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            timestamp TEXT,
            tracking_id INTEGER,
            vehicle_type TEXT,
            confidence REAL,
            direction TEXT
        )
        """
    )
    conn.commit()
    conn.close()


SESSION_ID = str(uuid.uuid4())
_last_saved_count = 0


def persist_new_detections():
    """Writes any newly counted detections (since last save) into SQLite."""
    global _last_saved_count
    if processor is None:
        return
    history = processor.counter.full_history
    new_entries = history[_last_saved_count:]
    if not new_entries:
        return
    conn = sqlite3.connect(config.DB_PATH)
    for entry in new_entries:
        conn.execute(
            "INSERT INTO detections (session_id, timestamp, tracking_id, vehicle_type, confidence, direction) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                SESSION_ID,
                entry["time"],
                entry["track_id"],
                entry["vehicle_type"],
                entry["confidence"],
                entry["direction"],
            ),
        )
    conn.commit()
    conn.close()
    _last_saved_count = len(history)


@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("Application startup complete. Database initialized at %s", config.DB_PATH)


@app.on_event("shutdown")
def on_shutdown():
    global processor
    if processor is not None:
        processor.stop()


# ---------------------------------------------------------------------------
# API: Upload
# ---------------------------------------------------------------------------
@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    global current_video_path

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in config.ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed types: "
                   f"{', '.join(sorted(config.ALLOWED_VIDEO_EXTENSIONS))}",
        )

    safe_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(config.UPLOADS_DIR, safe_name)

    try:
        with open(save_path, "wb") as out_file:
            while True:
                chunk = await file.read(1024 * 1024)  # 1 MB chunks, no full-RAM load
                if not chunk:
                    break
                out_file.write(chunk)
    except Exception as exc:
        logger.exception("Failed to save uploaded file")
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded video: {exc}")

    if os.path.getsize(save_path) == 0:
        os.remove(save_path)
        raise HTTPException(status_code=400, detail="Uploaded video file is empty.")

    current_video_path = save_path
    logger.info(f"Video uploaded: {save_path}")
    return {"message": "Video uploaded successfully", "filename": safe_name}


# ---------------------------------------------------------------------------
# API: Start / Stop / Reset
# ---------------------------------------------------------------------------
@app.post("/start")
async def start_processing(
    mode: str = "webcam",
    confidence: float = None,
    line_position: float = None,
    direction: str = None,
):
    """
    mode: "webcam" or "upload"
    """
    proc = get_processor()
    proc.configure(confidence=confidence, line_position=line_position, direction=direction)

    if mode == "webcam":
        source = 0
    elif mode == "upload":
        if not current_video_path or not os.path.isfile(current_video_path):
            raise HTTPException(status_code=400, detail="No uploaded video found. Please upload a video first.")
        source = current_video_path
    else:
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'webcam' or 'upload'.")

    ok, error = proc.start(source)
    if not ok:
        raise HTTPException(status_code=500, detail=error)

    return {"message": "Processing started", "mode": mode, "device": proc.device}


@app.post("/stop")
async def stop_processing():
    if processor is not None:
        processor.stop()
    return {"message": "Processing stopped"}


@app.post("/reset")
async def reset_counts():
    global _last_saved_count
    if processor is not None:
        processor.reset_counts()
    _last_saved_count = 0
    return {"message": "Counts reset"}


@app.post("/configure")
async def configure(confidence: float = None, line_position: float = None, direction: str = None):
    proc = get_processor()
    proc.configure(confidence=confidence, line_position=line_position, direction=direction)
    return {"message": "Configuration updated"}


# ---------------------------------------------------------------------------
# API: Stats
# ---------------------------------------------------------------------------
@app.get("/stats")
async def get_stats():
    if processor is None:
        return JSONResponse(
            {
                "total": 0, "cars": 0, "motorcycles": 0, "buses": 0, "trucks": 0,
                "active_tracks": 0, "fps": 0, "status": "stopped",
                "device": "cpu", "recent_detections": [], "flow_series": [], "error": None,
            }
        )
    persist_new_detections()
    return JSONResponse(processor.get_stats())


@app.get("/export")
async def export_csv():
    if processor is None:
        raise HTTPException(status_code=400, detail="No session data available yet.")
    csv_text = processor.counter.export_csv()
    filename = "vehicle_counts.csv"
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---------------------------------------------------------------------------
# API: Video streaming (MJPEG)
# ---------------------------------------------------------------------------
def mjpeg_generator():
    boundary = b"--frame"
    placeholder_interval = 0.2
    while True:
        if processor is not None:
            frame_bytes = processor.get_latest_jpeg()
        else:
            frame_bytes = None

        if frame_bytes is not None:
            yield (
                boundary + b"\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
            time.sleep(1.0 / config.TARGET_STREAM_FPS)
        else:
            time.sleep(placeholder_interval)


@app.get("/video")
async def video_feed():
    return StreamingResponse(
        mjpeg_generator(), media_type="multipart/x-mixed-replace; boundary=frame"
    )


# ---------------------------------------------------------------------------
# Frontend static files (serve at http://127.0.0.1:8000/)
# ---------------------------------------------------------------------------
FRONTEND_DIR = os.path.join(config.PROJECT_ROOT, "frontend")

if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    @app.get("/style.css")
    async def serve_css():
        return FileResponse(os.path.join(FRONTEND_DIR, "style.css"))

    @app.get("/app.js")
    async def serve_js():
        return FileResponse(os.path.join(FRONTEND_DIR, "app.js"))
else:
    logger.warning(f"Frontend directory not found at {FRONTEND_DIR}")
