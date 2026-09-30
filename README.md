# AI Vehicle Detection & Counting System

A complete, real-time vehicle detection and counting system that runs locally
on a Windows laptop, using YOLO (Ultralytics) for detection, ByteTrack for
multi-object tracking, and a vanilla HTML/CSS/JS dashboard served by FastAPI.

---

## 1. Project Overview

This application lets you:

- Open a browser dashboard.
- Use your webcam **or** upload a traffic video (MP4 / AVI / MOV / MKV).
- Detect cars, motorcycles, buses, and trucks in real time using a pretrained
  YOLOv8 model (no training required).
- Track each vehicle with a persistent ID across frames using ByteTrack.
- Count vehicles only once, when they cross a configurable virtual line —
  never by simply counting per-frame detections.
- Watch live statistics, charts, and a recent-detections table update without
  reloading the page.
- Export the full session's detection history as a CSV file.

Everything runs **locally** — no cloud services, no external database.

---

## 2. Features

- Real YOLO inference + OpenCV video processing (not a simulation).
- ByteTrack-based tracking with persistent per-vehicle IDs.
- Center-point line-crossing counting logic with duplicate-count prevention.
- Configurable counting line position and direction (Top→Bottom, Bottom→Top, Both).
- Configurable confidence threshold.
- Webcam mode and video-upload mode (frame-by-frame processing, no full-file RAM load).
- Live MJPEG video stream with bounding boxes, class, confidence, and ID overlays.
- Real-time stats: total, per-class counts, FPS, active track count.
- Vehicle distribution chart and traffic-flow-over-time chart (pure Canvas, no chart library).
- Recent-detections table (latest 50).
- CSV export of full session history.
- SQLite storage of every counted detection.
- Automatic CPU/GPU (CUDA) detection with graceful CPU fallback.
- Clean, modular, well-commented Python backend.

---

## 3. Technologies

**Frontend:** HTML5, CSS3, vanilla JavaScript, Fetch API, MJPEG streaming.
**Backend:** Python 3.10+, FastAPI, Uvicorn, OpenCV.
**ML/CV:** Ultralytics YOLOv8 (pretrained `yolov8n.pt`), ByteTrack (built into Ultralytics' `model.track()`).
**Storage:** SQLite (local file, no external DB).

---

## 4. System Architecture

```
Browser (index.html / app.js)
        │  Fetch API (upload/start/stop/reset/stats/export)
        │  <img> MJPEG stream (/video)
        ▼
FastAPI (backend/main.py)
        │
        ▼
VideoProcessor (backend/video_processor.py)
   ├── OpenCV VideoCapture (webcam or uploaded file)
   ├── VehicleDetector (backend/detector.py) — YOLOv8 + ByteTrack via model.track()
   ├── TrackManager (backend/tracker.py) — per-ID position history
   └── VehicleCounter (backend/counter.py) — line-crossing + duplicate prevention
        │
        ▼
Annotated frame → JPEG → MJPEG stream → Browser
        │
        ▼
SQLite (outputs/detections.db) — persisted counted detections
```

---

## 5. Requirements

- Windows 10/11
- Python 3.10 or newer (added to PATH)
- A working webcam (optional, only needed for webcam mode)
- ~2 GB free disk space (for Python packages + the pretrained model)
- Internet connection for the *first run only* (to install packages and
  auto-download the pretrained YOLO weights)
- NVIDIA GPU + CUDA: optional. The app automatically uses it if available,
  otherwise runs on CPU.

---

## 6. Installation (Windows)

Open **Command Prompt** or **PowerShell** in the project's root folder
(`vehicle-detection-counter/`) and run:

```bat
python -m venv venv
venv\Scripts\activate
pip install -r backend\requirements.txt
```

This installs FastAPI, Uvicorn, OpenCV, Ultralytics, and PyTorch (CPU build
by default — see Section 15 for GPU installation).

---

## 7. Python Virtual Environment Setup

```bat
python -m venv venv
venv\Scripts\activate
```

You should see `(venv)` appear in your prompt. Always activate the
environment before running the app.

---

## 8. Dependency Installation

```bat
pip install -r backend\requirements.txt
```

`backend/requirements.txt` contains pinned versions of: fastapi, uvicorn,
python-multipart, opencv-python, ultralytics, torch, torchvision, numpy.

---

## 9. Model Setup

No manual setup is required. On first run, Ultralytics automatically
downloads `yolov8n.pt` (a small, fast, pretrained COCO model — about 6 MB)
if it isn't already cached locally. This requires an internet connection
the very first time only.

The app detects these COCO classes out of the box:
`car`, `motorcycle`, `bus`, `truck`.

---

## 10. Running the Backend

From the project root (with the virtual environment activated):

```bat
python -m uvicorn backend.main:app --reload
```

Or simply double-click / run `run.bat`, which creates the virtual
environment (if missing), installs dependencies, and starts the server —
a single-command startup.

---

## 11. Opening the Frontend

Open your browser and go to:

```
http://127.0.0.1:8000
```

FastAPI serves the dashboard directly — no separate frontend server needed.

---

## 12. Webcam Usage

1. Select **Webcam** as the source (selected by default).
2. Click **Start Detection**.
3. Grant camera permission if your OS/browser prompts you (note: the webcam
   is accessed by the Python backend via OpenCV, not the browser, so any
   permission prompt will come from Windows itself).
4. The processed stream with bounding boxes and live counts appears in the
   Live Monitoring panel.

---

## 13. Video Upload Usage

1. Select **Upload Video**.
2. Choose an MP4, AVI, MOV, or MKV file.
3. Wait for the upload to complete (no visible progress bar is required for
   typical traffic clips; larger files take longer).
4. Click **Start Detection**. The video is processed frame by frame — it is
   never loaded fully into memory.

---

## 14. Custom Model Usage

To use your own trained YOLO model instead of the default pretrained one:

1. Place your `.pt` file at:
   ```
   backend/models/custom_model.pt
   ```
2. Restart the backend. `detector.py` automatically prefers
   `custom_model.pt` over the default pretrained model when it's present.
3. Make sure your custom model's class indices match (or update)
   `VEHICLE_CLASSES` in `backend/config.py` accordingly.

---

## 15. CPU / GPU Configuration

The app automatically detects CUDA via `torch.cuda.is_available()` and uses
the GPU when present; otherwise it falls back to CPU automatically. No
manual configuration is required. The active device is shown in the
dashboard's System Info panel and in the video overlay.

To enable GPU acceleration, install the CUDA-enabled PyTorch build that
matches your GPU/driver instead of the default CPU build, for example:

```bat
pip uninstall torch torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

(Check https://pytorch.org/get-started/locally/ for the command matching
your specific CUDA version.)

---

## 16. Troubleshooting

**ModuleNotFoundError**
Make sure the virtual environment is activated (`venv\Scripts\activate`)
and re-run `pip install -r backend\requirements.txt`.

**Camera not detected**
- Close other applications that might be using the webcam (Zoom, Teams, etc.).
- Check Windows Settings → Privacy → Camera → allow desktop apps to access the camera.
- Try a different webcam index by editing `source = 0` in `backend/main.py`'s
  `/start` handler to `1` or `2` if you have multiple cameras.

**Port already in use**
Run on a different port:
```bat
python -m uvicorn backend.main:app --port 8001
```
Then open `http://127.0.0.1:8001`.

**YOLO model download failure**
Ensure you have an internet connection on first run. If you're behind a
restrictive firewall/proxy, manually download `yolov8n.pt` from the
Ultralytics releases page and place it at `backend/models/yolov8n.pt`.

**Low FPS**
- Lower the processing resolution in `backend/config.py`
  (`PROCESSING_WIDTH` / `PROCESSING_HEIGHT`).
- Close other CPU-heavy applications.
- Consider a smaller/faster model if using a custom one.

**CUDA unavailable**
This is expected on laptops without an NVIDIA GPU — the app automatically
uses CPU and will say `Device: CPU` on the dashboard. This is normal.

**Browser connection error**
Confirm the backend terminal shows `Uvicorn running on http://127.0.0.1:8000`
and that no firewall is blocking local connections.

**Video not loading / stream frozen**
- Make sure you clicked **Start Detection** after selecting a source.
- Check the backend terminal / `logs/app.log` for error messages.
- For uploaded videos, confirm the file is not corrupted (try playing it in
  a media player first).

---

## 17. Project Structure

```
vehicle-detection-counter/
│
├── backend/
│   ├── main.py              # FastAPI app, routes, WebSocket/MJPEG, lifecycle
│   ├── detector.py          # YOLO loading + inference + device selection
│   ├── tracker.py           # Per-track state/history management
│   ├── counter.py           # Line-crossing counting logic, CSV export
│   ├── video_processor.py   # Capture loop, annotation drawing, FPS calc
│   ├── config.py            # All tunable settings in one place
│   ├── models/
│   │   └── (yolov8n.pt downloaded here automatically; custom_model.pt optional)
│   └── requirements.txt
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
│
├── uploads/                 # Uploaded videos land here
├── outputs/                 # detections.db (SQLite) lives here
├── logs/                    # app.log
│
├── README.md
└── run.bat
```

---

## 18. Future Improvements

- Multi-line / multi-zone counting for complex intersections.
- Speed estimation using calibrated real-world distances.
- Vehicle re-identification across camera cuts.
- Multi-camera support with a unified dashboard.
- Historical analytics dashboard (day/week/month trends) backed by the
  existing SQLite data.
- WebSocket-based binary frame streaming as an alternative to MJPEG for
  even lower latency.
- Authentication for multi-user deployments.

---

## Testing Checklist

1. Run `run.bat` (or the manual `uvicorn` command).
2. Open `http://127.0.0.1:8000` in your browser.
3. Select **Webcam**, click **Start Detection**.
4. Move a vehicle-like object (or a toy car / picture on a phone screen) in
   front of the camera, or switch to **Upload Video** and use a real traffic clip.
5. Verify bounding boxes appear around detected vehicles.
6. Verify each vehicle keeps a stable tracking ID across frames.
7. Verify the yellow counting line is visible on the video.
8. Verify counts increase only when a tracked vehicle's center crosses the line.
9. Click **Export CSV** and confirm `vehicle_counts.csv` downloads with the
   session's detection history.
