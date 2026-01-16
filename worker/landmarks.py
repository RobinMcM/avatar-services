"""
Face landmark detection utilities using MediaPipe Face Mesh.
CPU-optimized for anchor timeline generation.
"""
import cv2
import mediapipe as mp
import numpy as np
from typing import Optional, Dict, List, Tuple
import structlog

logger = structlog.get_logger()

# MediaPipe face mesh landmarks indices
# https://github.com/google/mediapipe/blob/master/mediapipe/modules/face_geometry/data/canonical_face_model_uv_visualization.png
LIPS_LANDMARKS = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95,
                  185, 40, 39, 37, 0, 267, 269, 270, 409, 415, 310, 311, 312, 13, 82, 81, 80, 191, 78]
EYE_LEFT_LANDMARKS = [33, 246, 161, 160, 159, 158, 157, 173, 133, 155, 154, 153, 145, 144, 163, 7]
EYE_RIGHT_LANDMARKS = [362, 398, 384, 385, 386, 387, 388, 466, 263, 249, 390, 373, 374, 380, 381, 382]


class FaceLandmarkDetector:
    """CPU-based face landmark detector using MediaPipe."""
    
    def __init__(self, static_image_mode=False, max_num_faces=1, min_detection_confidence=0.5):
        """Initialize MediaPipe Face Mesh."""
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=static_image_mode,
            max_num_faces=max_num_faces,
            refine_landmarks=True,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=0.5
        )
        logger.info("face_landmark_detector_initialized")
    
    def detect(self, image: np.ndarray) -> Optional[List]:
        """
        Detect facial landmarks in an image.
        
        Args:
            image: RGB image as numpy array (H, W, 3)
        
        Returns:
            List of landmark objects or None if no face detected
        """
        results = self.face_mesh.process(image)
        if results.multi_face_landmarks:
            return results.multi_face_landmarks
        return None
    
    def close(self):
        """Release resources."""
        self.face_mesh.close()


def get_landmark_coords(landmarks, indices: List[int], width: int, height: int) -> np.ndarray:
    """
    Extract coordinates for specific landmark indices.
    
    Args:
        landmarks: MediaPipe face landmarks
        indices: List of landmark indices to extract
        width: Image width
        height: Image height
    
    Returns:
        Array of shape (N, 2) with [x, y] coordinates
    """
    coords = []
    for idx in indices:
        lm = landmarks.landmark[idx]
        x = int(lm.x * width)
        y = int(lm.y * height)
        coords.append([x, y])
    return np.array(coords)


def compute_bbox_from_landmarks(coords: np.ndarray, padding: float = 1.3) -> Dict[str, int]:
    """
    Compute bounding box from landmark coordinates.
    
    Args:
        coords: Array of [x, y] coordinates
        padding: Expansion factor (1.3 = 30% padding)
    
    Returns:
        Dict with {x, y, w, h, cx, cy} - top-left corner, dimensions, and center
    """
    if len(coords) == 0:
        return None
    
    x_min, y_min = coords.min(axis=0)
    x_max, y_max = coords.max(axis=0)
    
    # Original bbox
    orig_w = x_max - x_min
    orig_h = y_max - y_min
    orig_cx = (x_min + x_max) / 2
    orig_cy = (y_min + y_max) / 2
    
    # Expand by padding factor
    new_w = int(orig_w * padding)
    new_h = int(orig_h * padding)
    
    # Compute new top-left corner (centered expansion)
    new_x = int(orig_cx - new_w / 2)
    new_y = int(orig_cy - new_h / 2)
    
    return {
        'x': new_x,
        'y': new_y,
        'w': new_w,
        'h': new_h,
        'cx': int(orig_cx),
        'cy': int(orig_cy)
    }


def extract_mouth_anchor(landmarks, width: int, height: int, padding: float = 1.5) -> Optional[Dict]:
    """
    Extract mouth anchor box from face landmarks.
    
    Args:
        landmarks: MediaPipe face landmarks
        width: Frame width
        height: Frame height
        padding: Expansion factor (1.5 = 50% padding)
    
    Returns:
        Anchor dict or None if failed
    """
    try:
        coords = get_landmark_coords(landmarks, LIPS_LANDMARKS, width, height)
        return compute_bbox_from_landmarks(coords, padding)
    except Exception as e:
        logger.warning("failed_to_extract_mouth_anchor", error=str(e))
        return None


def extract_eyes_anchor(landmarks, width: int, height: int, padding: float = 1.3) -> Optional[Dict]:
    """
    Extract eyes anchor box from face landmarks.
    
    Args:
        landmarks: MediaPipe face landmarks
        width: Frame width
        height: Frame height
        padding: Expansion factor (1.3 = 30% padding)
    
    Returns:
        Anchor dict or None if failed
    """
    try:
        left_coords = get_landmark_coords(landmarks, EYE_LEFT_LANDMARKS, width, height)
        right_coords = get_landmark_coords(landmarks, EYE_RIGHT_LANDMARKS, width, height)
        all_coords = np.concatenate([left_coords, right_coords])
        return compute_bbox_from_landmarks(all_coords, padding)
    except Exception as e:
        logger.warning("failed_to_extract_eyes_anchor", error=str(e))
        return None


def clamp_bbox(bbox: Dict, max_width: int, max_height: int) -> Dict:
    """
    Clamp bounding box to frame boundaries.
    
    Args:
        bbox: Bounding box dict {x, y, w, h, cx, cy}
        max_width: Frame width
        max_height: Frame height
    
    Returns:
        Clamped bounding box
    """
    x = max(0, bbox['x'])
    y = max(0, bbox['y'])
    w = min(bbox['w'], max_width - x)
    h = min(bbox['h'], max_height - y)
    
    return {
        'x': x,
        'y': y,
        'w': w,
        'h': h,
        'cx': bbox['cx'],
        'cy': bbox['cy']
    }
