"""
Capture Processor - Generates avatar packs from recorded videos.
MVP implementation with deterministic pipeline using MediaPipe landmarks.
"""
import os
import sys
import json
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import structlog

# Import Phase 1 landmark code
from landmarks import (
    FaceLandmarkDetector,
    extract_mouth_anchor,
    extract_eyes_anchor,
    clamp_bbox
)
from anchor_timeline import generate_anchor_timeline

logger = structlog.get_logger()

# Timeline constants (matching capture.js)
TIMELINE_MAP = {
    'idle': (1.0, 5.0),
    'rest': (6.0,),
    'aa': (8.0,),
    'ee': (10.0,),
    'oh': (12.0,),
    'oo': (14.0,),
    'ff': (16.0,),
    'th': (18.0,),
    'eyes_open': (26.0,),
    'eyes_half': (28.0,),
    'eyes_closed': (30.0,)
}

# Target dimensions
TARGET_WIDTH = 512
TARGET_HEIGHT = 640
MOUTH_FRAME_WIDTH = 320
MOUTH_FRAME_HEIGHT = 240
EYES_FRAME_WIDTH = 320
EYES_FRAME_HEIGHT = 120


def run_command(cmd: List[str], desc: str) -> bool:
    """Run a shell command with logging."""
    try:
        logger.info(f"running_{desc}", command=' '.join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"{desc}_failed", error=e.stderr, stdout=e.stdout)
        return False


def update_job_status(redis_client, job_id: str, status: str, progress: int, log_message: str):
    """Update job status in Redis."""
    status_key = f"avatar:capture:status:{job_id}"
    
    # Get current status
    status_json = redis_client.get(status_key)
    if status_json:
        status_data = json.loads(status_json)
    else:
        status_data = {'logs': []}
    
    # Update fields
    status_data['status'] = status
    status_data['progress'] = progress
    
    # Add log
    if log_message:
        if 'logs' not in status_data:
            status_data['logs'] = []
        status_data['logs'].append(log_message)
    
    # Save
    redis_client.set(status_key, json.dumps(status_data), ex=3600)
    logger.info("job_status_updated", job_id=job_id, status=status, progress=progress)


def normalize_video(input_path: str, output_path: str) -> bool:
    """Normalize video to 512x640, 30fps."""
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-vf', f'scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=increase,crop={TARGET_WIDTH}:{TARGET_HEIGHT}',
        '-r', '30',
        '-c:v', 'libvpx-vp9',
        '-b:v', '0',
        '-crf', '30',
        '-c:a', 'libopus',
        '-b:a', '64k',
        output_path
    ]
    return run_command(cmd, "normalize_video")


def extract_base_face(video_path: str, output_path: str, timestamp: float = 2.0) -> bool:
    """Extract a single frame as base face image."""
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(timestamp),
        '-i', video_path,
        '-vframes', '1',
        '-q:v', '2',
        output_path
    ]
    return run_command(cmd, "extract_base_face")


def extract_idle_video(input_path: str, output_path: str, start: float, end: float) -> bool:
    """Extract idle loop segment."""
    duration = end - start
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start),
        '-i', input_path,
        '-t', str(duration),
        '-c:v', 'libvpx-vp9',
        '-b:v', '0',
        '-crf', '35',
        '-an',  # No audio for idle
        output_path
    ]
    return run_command(cmd, "extract_idle_video")


def extract_frame_at_timestamp(video_path: str, timestamp: float) -> Optional[np.ndarray]:
    """Extract a single frame at a specific timestamp."""
    cap = cv2.VideoCapture(video_path)
    
    # Set position
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_num = int(timestamp * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
    
    ret, frame = cap.read()
    cap.release()
    
    if ret:
        # Convert BGR to RGB
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return None


def crop_and_resize(image: np.ndarray, bbox: Dict, target_width: int, target_height: int) -> np.ndarray:
    """Crop region from image and resize."""
    x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
    
    # Clamp to image bounds
    img_h, img_w = image.shape[:2]
    x = max(0, min(x, img_w - 1))
    y = max(0, min(y, img_h - 1))
    w = min(w, img_w - x)
    h = min(h, img_h - y)
    
    # Crop
    cropped = image[y:y+h, x:x+w]
    
    # Resize
    resized = cv2.resize(cropped, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)
    
    return resized


def create_ellipse_mask(width: int, height: int, feather_px: int = 12) -> np.ndarray:
    """Create a simple elliptical mask with feathered edges (MVP)."""
    # Create PIL image
    mask = Image.new('L', (width, height), 0)
    draw = ImageDraw.Draw(mask)
    
    # Draw ellipse (slightly smaller to allow feathering)
    margin = feather_px
    draw.ellipse([margin, margin, width - margin, height - margin], fill=255)
    
    # Apply Gaussian blur for feathering
    mask = mask.filter(ImageFilter.GaussianBlur(radius=feather_px))
    
    return np.array(mask)


def process_capture_job(job_data: Dict, redis_client) -> Dict:
    """
    Main processing pipeline for capture jobs.
    
    Returns status dict with results or error.
    """
    job_id = job_data['job_id']
    capture_id = job_data['capture_id']
    avatar_id = job_data['avatar_id']
    capture_path = job_data['capture_path']
    avatars_dir = job_data['avatars_dir']
    
    logger.info("processing_capture_job", job_id=job_id, avatar_id=avatar_id)
    
    # Create avatar directory
    avatar_dir = os.path.join(avatars_dir, avatar_id)
    os.makedirs(avatar_dir, exist_ok=True)
    
    try:
        # Step 1: Normalize video
        update_job_status(redis_client, job_id, 'processing', 10, '→ Normalizing video...')
        normalized_path = os.path.join(avatar_dir, 'normalized.webm')
        if not normalize_video(capture_path, normalized_path):
            raise Exception("Video normalization failed")
        
        # Step 2: Extract base face
        update_job_status(redis_client, job_id, 'processing', 20, '→ Extracting base face...')
        base_face_path = os.path.join(avatar_dir, 'base_face.png')
        if not extract_base_face(normalized_path, base_face_path, timestamp=2.0):
            raise Exception("Base face extraction failed")
        
        # Step 3: Extract idle video
        update_job_status(redis_client, job_id, 'processing', 30, '→ Extracting idle loop...')
        idle_start, idle_end = TIMELINE_MAP['idle']
        idle_path = os.path.join(avatar_dir, 'idle.webm')
        if not extract_idle_video(normalized_path, idle_path, idle_start, idle_end):
            raise Exception("Idle video extraction failed")
        
        # Step 4: Generate anchor timeline
        update_job_status(redis_client, job_id, 'processing', 40, '→ Detecting face landmarks...')
        anchors_path = os.path.join(avatar_dir, 'anchors_timeline.json')
        timeline_data = generate_anchor_timeline(
            video_path=idle_path,
            output_path=anchors_path,
            sample_every_n_frames=3,
            target_width=TARGET_WIDTH,
            target_height=TARGET_HEIGHT
        )
        logger.info("anchor_timeline_generated", frames=len(timeline_data['frames']))
        
        # Step 5: Extract viseme frames using landmarks
        update_job_status(redis_client, job_id, 'processing', 50, '→ Extracting mouth visemes...')
        viseme_frames = extract_viseme_frames(normalized_path, avatar_dir)
        
        # Step 6: Extract eye frames
        update_job_status(redis_client, job_id, 'processing', 65, '→ Extracting eye states...')
        eye_frames = extract_eye_frames(normalized_path, avatar_dir)
        save_eye_frames(eye_frames, avatar_dir)
        
        # Step 7: Create masks
        update_job_status(redis_client, job_id, 'processing', 75, '→ Generating masks...')
        create_masks(avatar_dir)
        
        # Step 8: Build spritesheet
        update_job_status(redis_client, job_id, 'processing', 85, '→ Building mouth spritesheet...')
        create_mouth_spritesheet(viseme_frames, avatar_dir)
        
        # Step 9: Generate manifest
        update_job_status(redis_client, job_id, 'processing', 90, '→ Writing manifest...')
        manifest_path = create_manifest(avatar_id, avatar_dir, timeline_data)
        
        # Step 10: Create ZIP
        update_job_status(redis_client, job_id, 'processing', 95, '→ Creating ZIP archive...')
        zip_path = create_zip(avatar_dir, avatars_dir, avatar_id)
        
        # Complete
        update_job_status(redis_client, job_id, 'completed', 100, '✓ Avatar pack generated successfully!')
        
        # Clean up normalized video
        if os.path.exists(normalized_path):
            os.remove(normalized_path)
        
        return {
            'status': 'completed',
            'avatar_id': avatar_id,
            'manifest_url': f'/avatars/{avatar_id}/manifest.json',
            'zip_url': f'/avatars/{avatar_id}.zip'
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error("capture_processing_failed", job_id=job_id, error=error_msg, exc_info=True)
        update_job_status(redis_client, job_id, 'failed', 0, f'✗ Error: {error_msg}')
        return {
            'status': 'failed',
            'error': error_msg
        }


def extract_viseme_frames(video_path: str, avatar_dir: str) -> Dict[str, np.ndarray]:
    """Extract mouth frames for each viseme using landmarks."""
    viseme_frames = {}
    detector = FaceLandmarkDetector(static_image_mode=False)
    
    visemes = ['rest', 'aa', 'ee', 'oh', 'oo', 'ff', 'th']
    
    try:
        for viseme in visemes:
            if viseme not in TIMELINE_MAP:
                logger.warning(f"viseme_{viseme}_not_in_timeline")
                continue
            
            timestamp = TIMELINE_MAP[viseme][0]
            
            # Extract frame
            frame = extract_frame_at_timestamp(video_path, timestamp)
            if frame is None:
                logger.warning(f"failed_to_extract_{viseme}_frame")
                continue
            
            # Detect landmarks
            landmarks_list = detector.detect(frame)
            if not landmarks_list or len(landmarks_list) == 0:
                logger.warning(f"no_face_detected_for_{viseme}")
                continue
            
            landmarks = landmarks_list[0]
            
            # Get mouth anchor
            mouth_anchor = extract_mouth_anchor(landmarks, TARGET_WIDTH, TARGET_HEIGHT, padding=1.5)
            if not mouth_anchor:
                logger.warning(f"failed_to_extract_mouth_anchor_for_{viseme}")
                continue
            
            # Clamp bbox
            mouth_anchor = clamp_bbox(mouth_anchor, TARGET_WIDTH, TARGET_HEIGHT)
            
            # Crop and resize
            mouth_img = crop_and_resize(frame, mouth_anchor, MOUTH_FRAME_WIDTH, MOUTH_FRAME_HEIGHT)
            
            # Store
            viseme_frames[viseme] = mouth_img
            
            logger.info(f"extracted_{viseme}_frame", bbox=mouth_anchor)
    
    finally:
        detector.close()
    
    return viseme_frames


def extract_eye_frames(video_path: str, avatar_dir: str) -> Dict[str, np.ndarray]:
    """Extract eye frames for open/half/closed states."""
    eye_frames = {}
    detector = FaceLandmarkDetector(static_image_mode=False)
    
    eye_states = ['eyes_open', 'eyes_half', 'eyes_closed']
    
    try:
        for state in eye_states:
            if state not in TIMELINE_MAP:
                continue
            
            timestamp = TIMELINE_MAP[state][0]
            
            # Extract frame
            frame = extract_frame_at_timestamp(video_path, timestamp)
            if frame is None:
                continue
            
            # Detect landmarks
            landmarks_list = detector.detect(frame)
            if not landmarks_list:
                continue
            
            landmarks = landmarks_list[0]
            
            # Get eyes anchor
            eyes_anchor = extract_eyes_anchor(landmarks, TARGET_WIDTH, TARGET_HEIGHT, padding=1.3)
            if not eyes_anchor:
                continue
            
            # Clamp bbox
            eyes_anchor = clamp_bbox(eyes_anchor, TARGET_WIDTH, TARGET_HEIGHT)
            
            # Crop and resize
            eyes_img = crop_and_resize(frame, eyes_anchor, EYES_FRAME_WIDTH, EYES_FRAME_HEIGHT)
            
            # Store with simple key
            key = state.replace('eyes_', '')
            eye_frames[key] = eyes_img
            
            logger.info(f"extracted_{state}_frame", bbox=eyes_anchor)
    
    finally:
        detector.close()
    
    return eye_frames


def create_masks(avatar_dir: str):
    """Create simple elliptical masks for MVP."""
    # Mouth mask
    mouth_mask = create_ellipse_mask(MOUTH_FRAME_WIDTH, MOUTH_FRAME_HEIGHT, feather_px=12)
    mouth_mask_path = os.path.join(avatar_dir, 'mouth_mask.png')
    Image.fromarray(mouth_mask).save(mouth_mask_path)
    
    # Eyes mask
    eyes_mask = create_ellipse_mask(EYES_FRAME_WIDTH, EYES_FRAME_HEIGHT, feather_px=8)
    eyes_mask_path = os.path.join(avatar_dir, 'eyes_mask.png')
    Image.fromarray(eyes_mask).save(eyes_mask_path)
    
    logger.info("masks_created")


def create_mouth_spritesheet(viseme_frames: Dict[str, np.ndarray], avatar_dir: str):
    """Create horizontal spritesheet from viseme frames."""
    viseme_order = ['rest', 'aa', 'ee', 'oh', 'oo', 'ff', 'th']
    
    # Create spritesheet canvas
    sheet_width = MOUTH_FRAME_WIDTH * len(viseme_order)
    sheet_height = MOUTH_FRAME_HEIGHT
    spritesheet = np.zeros((sheet_height, sheet_width, 3), dtype=np.uint8)
    
    for i, viseme in enumerate(viseme_order):
        if viseme in viseme_frames:
            x_offset = i * MOUTH_FRAME_WIDTH
            spritesheet[:, x_offset:x_offset + MOUTH_FRAME_WIDTH] = viseme_frames[viseme]
        else:
            logger.warning(f"missing_viseme_{viseme}_using_black")
    
    # Save
    spritesheet_path = os.path.join(avatar_dir, 'mouth_sprites.png')
    Image.fromarray(spritesheet).save(spritesheet_path)
    
    logger.info("spritesheet_created", width=sheet_width, height=sheet_height)


def save_eye_frames(eye_frames: Dict[str, np.ndarray], avatar_dir: str):
    """Save individual eye state frames."""
    for state, frame in eye_frames.items():
        frame_path = os.path.join(avatar_dir, f'eyes_{state}.png')
        Image.fromarray(frame).save(frame_path)
        logger.info(f"saved_eye_frame_{state}", path=frame_path)


def create_manifest(avatar_id: str, avatar_dir: str, timeline_data: Dict) -> str:
    """Create manifest.json for the avatar pack."""
    
    # Get default anchors from timeline (use first frame)
    default_mouth_anchor = {'x': 176, 'y': 400, 'w': MOUTH_FRAME_WIDTH, 'h': MOUTH_FRAME_HEIGHT}
    default_eyes_anchor = {'x': 96, 'y': 240, 'w': EYES_FRAME_WIDTH, 'h': EYES_FRAME_HEIGHT}
    
    if timeline_data and 'frames' in timeline_data and len(timeline_data['frames']) > 0:
        first_frame = timeline_data['frames'][0]
        if 'mouth' in first_frame:
            default_mouth_anchor = first_frame['mouth']
        if 'eyes' in first_frame:
            default_eyes_anchor = first_frame['eyes']
    
    manifest = {
        'id': avatar_id,
        'displayName': avatar_id.replace('_', ' ').title(),
        'version': '1.0.0',
        'description': 'Generated from Capture Studio',
        'base': {
            'type': 'image',
            'src': 'base_face.png',
            'width': TARGET_WIDTH,
            'height': TARGET_HEIGHT,
            'idleVideo': 'idle.webm'
        },
        'mouth': {
            'spritesheet': 'mouth_sprites.png',
            'mask': 'mouth_mask.png',
            'frameWidth': MOUTH_FRAME_WIDTH,
            'frameHeight': MOUTH_FRAME_HEIGHT,
            'visemes': ['REST', 'AA', 'EE', 'OH', 'OO', 'FF', 'TH'],
            'anchor': default_mouth_anchor,
            'featherPx': 12,
            'blendMode': 'normal'
        },
        'eyes': {
            'frames': {
                'open': 'eyes_open.png',
                'half': 'eyes_half.png',
                'closed': 'eyes_closed.png'
            },
            'mask': 'eyes_mask.png',
            'anchor': default_eyes_anchor,
            'pupil': {
                'enabled': True,
                'maxOffsetX': 8,
                'maxOffsetY': 6
            },
            'featherPx': 8,
            'blendMode': 'normal'
        },
        'mapping': {
            'REST': 'REST',
            'AA': 'AA',
            'EE': 'EE',
            'OH': 'OH',
            'OO': 'OO',
            'FF': 'FF',
            'TH': 'TH'
        },
        'microMotion': {
            'enabled': True,
            'headBobAmplitude': 2,
            'headBobFrequency': 0.5,
            'headTiltAmplitude': 0.8,
            'breathingScale': 0.003,
            'breathingFrequency': 0.25
        }
    }
    
    manifest_path = os.path.join(avatar_dir, 'manifest.json')
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    logger.info("manifest_created", path=manifest_path)
    return manifest_path


def create_zip(avatar_dir: str, avatars_dir: str, avatar_id: str) -> str:
    """Create ZIP archive of avatar pack."""
    zip_path = os.path.join(avatars_dir, f'{avatar_id}.zip')
    
    # Use shutil to create zip
    import zipfile
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(avatar_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, avatar_dir)
                zipf.write(file_path, arcname)
    
    logger.info("zip_created", path=zip_path)
    return zip_path
