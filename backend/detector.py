"""
detector.py
-----------
Responsible for:
  * Loading the YOLO model (pretrained or custom)
  * Selecting the compute device (CPU or CUDA, automatically)
  * Running inference + tracking (Ultralytics' built-in tracker,
    which uses ByteTrack under the hood) on a single frame
  * Returning a clean, structured list of detections

This module deliberately hides all Ultralytics-specific details from the
rest of the application (video_processor.py only calls `detect_and_track`).
"""

import logging
import os

import torch
from ultralytics import YOLO

import config

logger = logging.getLogger("vehicle_detector")


class VehicleDetector:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_path = self._resolve_model_path()
        self.model = self._load_model(self.model_path)
        self.class_map = config.VEHICLE_CLASSES  # {coco_id: name}
        logger.info(f"Detector initialized. Device={self.device}, model={self.model_path}")

    def _resolve_model_path(self) -> str:
        """
        Decide which weights file to load:
        1. A custom model at backend/models/custom_model.pt (if present and enabled)
        2. The default pretrained model (auto-downloaded by Ultralytics if missing)
        """
        if config.USE_CUSTOM_MODEL_IF_PRESENT and os.path.isfile(config.CUSTOM_MODEL_PATH):
            logger.info("Custom model found — using custom_model.pt")
            return config.CUSTOM_MODEL_PATH
        return config.MODEL_PATH

    def _load_model(self, model_path: str) -> YOLO:
        try:
            # If the default pretrained weights are not present locally,
            # passing the bare name (e.g. "yolov8n.pt") lets Ultralytics
            # download it automatically into its cache on first run.
            if not os.path.isfile(model_path) and model_path == config.MODEL_PATH:
                logger.info(
                    f"{config.DEFAULT_MODEL_NAME} not found locally. "
                    "Ultralytics will download it automatically on first run "
                    "(requires an internet connection one time only)."
                )
                model = YOLO(config.DEFAULT_MODEL_NAME)
                # Cache the downloaded weights inside our models/ folder for next time.
                try:
                    downloaded_path = model.ckpt_path if hasattr(model, "ckpt_path") else None
                except Exception:
                    downloaded_path = None
            else:
                model = YOLO(model_path)

            model.to(self.device)
            return model
        except Exception as exc:
            logger.error(f"Failed to load YOLO model: {exc}")
            raise RuntimeError(
                f"Could not load YOLO model from '{model_path}'. "
                f"Make sure the file exists and is a valid Ultralytics .pt model. "
                f"Original error: {exc}"
            )

    def reload_model(self, model_path: str = None):
        """Allows switching to a custom-trained model at runtime."""
        path = model_path or self._resolve_model_path()
        self.model = self._load_model(path)
        self.model_path = path

    def detect_and_track(self, frame, confidence_threshold: float):
        """
        Runs YOLO detection + ByteTrack tracking on a single BGR frame.

        Returns a list of dicts:
            {
                "track_id": int,
                "class_id": int,
                "class_name": str,
                "confidence": float,
                "bbox": (x1, y1, x2, y2),
                "center": (cx, cy),
            }
        """
        results = self.model.track(
            source=frame,
            persist=True,
            conf=confidence_threshold,
            classes=list(self.class_map.keys()),
            tracker=config.TRACKER_CONFIG,
            device=self.device,
            verbose=False,
        )

        detections = []
        if not results:
            return detections

        result = results[0]
        boxes = result.boxes
        if boxes is None or boxes.id is None:
            return detections

        xyxy = boxes.xyxy.cpu().numpy()
        track_ids = boxes.id.cpu().numpy().astype(int)
        confidences = boxes.conf.cpu().numpy()
        class_ids = boxes.cls.cpu().numpy().astype(int)

        for i in range(len(track_ids)):
            class_id = int(class_ids[i])
            if class_id not in self.class_map:
                continue
            x1, y1, x2, y2 = xyxy[i]
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            detections.append(
                {
                    "track_id": int(track_ids[i]),
                    "class_id": class_id,
                    "class_name": self.class_map[class_id],
                    "confidence": float(confidences[i]),
                    "bbox": (float(x1), float(y1), float(x2), float(y2)),
                    "center": (float(cx), float(cy)),
                }
            )
        return detections
