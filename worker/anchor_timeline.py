#!/usr/bin/env python3
"""
Anchor Timeline Generator
Generates anchor_timeline.json from an idle video using MediaPipe face landmarks.
"""
import os
import sys
import json
import argparse
import cv2
import structlog
from pathlib import Path
from typing import Dict, List, Optional

from landmarks import (
    FaceLandmarkDetector,
    extract_mouth_anchor,
    extract_eyes_anchor,
    clamp_bbox
)

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()


def generate_anchor_timeline(
    video_path: str,
    output_path: str,
    sample_every_n_frames: int = 3,
    target_width: int = 512,
    target_height: int = 640,
    mouth_padding: float = 1.5,
    eyes_padding: float = 1.3
) -> Dict:
    """
    Generate anchor timeline from video file.
    
    Args:
        video_path: Path to input video (idle loop)
        output_path: Path to output JSON file
        sample_every_n_frames: Sample rate (process every Nth frame)
        target_width: Target frame width for coordinate space
        target_height: Target frame height for coordinate space
        mouth_padding: Mouth bbox expansion factor
        eyes_padding: Eyes bbox expansion factor
    
    Returns:
        Timeline dictionary
    """
    logger.info("generating_anchor_timeline", video_path=video_path, output_path=output_path)
    
    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Failed to open video: {video_path}")
    
    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    orig_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    logger.info(
        "video_properties",
        fps=fps,
        frame_count=frame_count,
        width=orig_width,
        height=orig_height
    )
    
    # Initialize face detector
    detector = FaceLandmarkDetector(static_image_mode=False, max_num_faces=1)
    
    # Process frames
    timeline_frames = []
    frame_idx = 0
    detected_count = 0
    skipped_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Sample every N frames
            if frame_idx % sample_every_n_frames == 0:
                # Convert BGR to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Detect landmarks
                face_landmarks = detector.detect(rgb_frame)
                
                if face_landmarks and len(face_landmarks) > 0:
                    # Use first face
                    landmarks = face_landmarks[0]
                    
                    # Extract anchors
                    mouth_anchor = extract_mouth_anchor(
                        landmarks, orig_width, orig_height, mouth_padding
                    )
                    eyes_anchor = extract_eyes_anchor(
                        landmarks, orig_width, orig_height, eyes_padding
                    )
                    
                    if mouth_anchor and eyes_anchor:
                        # Clamp to frame boundaries
                        mouth_anchor = clamp_bbox(mouth_anchor, orig_width, orig_height)
                        eyes_anchor = clamp_bbox(eyes_anchor, orig_width, orig_height)
                        
                        # Scale coordinates to target resolution if needed
                        scale_x = target_width / orig_width
                        scale_y = target_height / orig_height
                        
                        if scale_x != 1.0 or scale_y != 1.0:
                            mouth_anchor = scale_anchor(mouth_anchor, scale_x, scale_y)
                            eyes_anchor = scale_anchor(eyes_anchor, scale_x, scale_y)
                        
                        # Add to timeline
                        timeline_frames.append({
                            'frame': frame_idx,
                            'time_ms': int((frame_idx / fps) * 1000),
                            'mouth': mouth_anchor,
                            'eyes': eyes_anchor
                        })
                        detected_count += 1
                    else:
                        logger.warning("failed_to_extract_anchors", frame=frame_idx)
                        skipped_count += 1
                else:
                    logger.warning("no_face_detected", frame=frame_idx)
                    skipped_count += 1
            
            frame_idx += 1
            
            # Progress indicator
            if frame_idx % 30 == 0:
                logger.info("processing", frame=frame_idx, total=frame_count)
    
    finally:
        cap.release()
        detector.close()
    
    logger.info(
        "processing_complete",
        total_frames=frame_idx,
        sampled_frames=detected_count,
        skipped_frames=skipped_count
    )
    
    # Build timeline document
    timeline = {
        'version': 1,
        'source': {
            'video': os.path.basename(video_path),
            'fps': fps,
            'frame_count': frame_count,
            'width': orig_width,
            'height': orig_height,
            'sample_every_n_frames': sample_every_n_frames
        },
        'target': {
            'width': target_width,
            'height': target_height
        },
        'config': {
            'mouth_padding': mouth_padding,
            'eyes_padding': eyes_padding
        },
        'frames': timeline_frames
    }
    
    # Write to file
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(timeline, f, indent=2)
    
    logger.info("timeline_saved", output_path=output_path, frame_count=len(timeline_frames))
    
    return timeline


def scale_anchor(anchor: Dict, scale_x: float, scale_y: float) -> Dict:
    """Scale anchor coordinates to different resolution."""
    return {
        'x': int(anchor['x'] * scale_x),
        'y': int(anchor['y'] * scale_y),
        'w': int(anchor['w'] * scale_x),
        'h': int(anchor['h'] * scale_y),
        'cx': int(anchor['cx'] * scale_x),
        'cy': int(anchor['cy'] * scale_y)
    }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Generate anchor timeline from idle video'
    )
    parser.add_argument(
        '--avatar-id',
        required=True,
        help='Avatar ID (e.g., realistic_female_v1)'
    )
    parser.add_argument(
        '--input',
        default='idle.webm',
        help='Input video filename (default: idle.webm)'
    )
    parser.add_argument(
        '--output',
        default='anchors_timeline.json',
        help='Output JSON filename (default: anchors_timeline.json)'
    )
    parser.add_argument(
        '--sample-rate',
        type=int,
        default=3,
        help='Sample every N frames (default: 3)'
    )
    parser.add_argument(
        '--target-width',
        type=int,
        default=512,
        help='Target coordinate space width (default: 512)'
    )
    parser.add_argument(
        '--target-height',
        type=int,
        default=640,
        help='Target coordinate space height (default: 640)'
    )
    parser.add_argument(
        '--mouth-padding',
        type=float,
        default=1.5,
        help='Mouth bbox expansion factor (default: 1.5)'
    )
    parser.add_argument(
        '--eyes-padding',
        type=float,
        default=1.3,
        help='Eyes bbox expansion factor (default: 1.3)'
    )
    parser.add_argument(
        '--base-path',
        default='/usr/share/nginx/html/avatars',
        help='Base path for avatars (default: /usr/share/nginx/html/avatars)'
    )
    
    args = parser.parse_args()
    
    # Construct paths
    avatar_dir = os.path.join(args.base_path, args.avatar_id)
    video_path = os.path.join(avatar_dir, args.input)
    output_path = os.path.join(avatar_dir, args.output)
    
    if not os.path.exists(video_path):
        logger.error("video_not_found", path=video_path)
        sys.exit(1)
    
    try:
        timeline = generate_anchor_timeline(
            video_path=video_path,
            output_path=output_path,
            sample_every_n_frames=args.sample_rate,
            target_width=args.target_width,
            target_height=args.target_height,
            mouth_padding=args.mouth_padding,
            eyes_padding=args.eyes_padding
        )
        
        print(f"\n✓ Anchor timeline generated successfully")
        print(f"  Output: {output_path}")
        print(f"  Frames: {len(timeline['frames'])}")
        print(f"\nTo verify, open the web demo and enable 'Show Tracking Anchors'")
        
    except Exception as e:
        logger.error("failed_to_generate_timeline", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
