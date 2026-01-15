#!/usr/bin/env python3
"""
Create Avatar Pack from Source Photo

This script helps you convert a source photo into avatar pack assets.

Usage:
    python3 create_avatar_from_photo.py source_face.jpg output_dir/
    
Requirements:
    pip install Pillow numpy opencv-python
"""

import sys
import os
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import argparse

def create_base_face(source_img, output_path, target_size=(512, 640)):
    """Create base face from source image"""
    print("Creating base face...")
    
    # Resize and crop to target size
    img = source_img.copy()
    
    # Calculate crop to get face centered
    width, height = img.size
    aspect = target_size[0] / target_size[1]
    
    if width / height > aspect:
        # Image is wider, crop width
        new_width = int(height * aspect)
        left = (width - new_width) // 2
        img = img.crop((left, 0, left + new_width, height))
    else:
        # Image is taller, crop height
        new_height = int(width / aspect)
        top = (height - new_height) // 2
        img = img.crop((0, top, width, top + new_height))
    
    # Resize to target
    img = img.resize(target_size, Image.LANCZOS)
    
    # Enhance slightly
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.1)
    
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(1.2)
    
    # Convert to RGBA
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    img.save(output_path, 'PNG', optimize=True)
    print(f"✓ Saved: {output_path}")
    return img

def extract_mouth_region(source_img, mouth_bbox, output_path, size=(160, 120)):
    """Extract and process mouth region"""
    print("Extracting mouth region...")
    
    # Crop mouth area
    mouth = source_img.crop(mouth_bbox)
    mouth = mouth.resize(size, Image.LANCZOS)
    
    # Enhance
    enhancer = ImageEnhance.Contrast(mouth)
    mouth = enhancer.enhance(1.15)
    
    if mouth.mode != 'RGBA':
        mouth = mouth.convert('RGBA')
    
    mouth.save(output_path, 'PNG', optimize=True)
    print(f"✓ Saved: {output_path}")
    return mouth

def create_mouth_variations(base_mouth, output_dir):
    """Create mouth viseme variations from base"""
    print("Creating mouth variations...")
    
    visemes = ['REST', 'AA', 'EE', 'OH', 'OO', 'FF', 'TH']
    
    # For demo, we'll create variations by adjusting the base
    # In production, you'd extract these from different photos/video frames
    
    sprites = []
    for i, viseme in enumerate(visemes):
        mouth = base_mouth.copy()
        
        # Apply transformations based on viseme
        if viseme == 'AA':  # Open wide
            mouth = mouth.resize((160, 140), Image.LANCZOS)
            mouth = mouth.crop((0, 10, 160, 130))
        elif viseme == 'EE':  # Wide smile
            mouth = mouth.resize((180, 110), Image.LANCZOS)
            mouth = mouth.crop((10, 0, 170, 120))
        elif viseme == 'OH':  # Round
            mouth = mouth.resize((140, 130), Image.LANCZOS)
            mouth = mouth.crop((0, 5, 140, 125))
            # Paste centered
            temp = Image.new('RGBA', (160, 120), (0, 0, 0, 0))
            temp.paste(mouth, (10, 0))
            mouth = temp
        elif viseme == 'OO':  # Tight round
            mouth = mouth.resize((120, 120), Image.LANCZOS)
            temp = Image.new('RGBA', (160, 120), (0, 0, 0, 0))
            temp.paste(mouth, (20, 0))
            mouth = temp
        elif viseme == 'FF':  # Flat
            mouth = mouth.resize((170, 100), Image.LANCZOS)
            mouth = mouth.crop((5, 0, 165, 100))
            temp = Image.new('RGBA', (160, 120), (0, 0, 0, 0))
            temp.paste(mouth, (0, 10))
            mouth = temp
        
        # Ensure correct size
        if mouth.size != (160, 120):
            temp = Image.new('RGBA', (160, 120), (0, 0, 0, 0))
            temp.paste(mouth, ((160 - mouth.width) // 2, (120 - mouth.height) // 2))
            mouth = temp
        
        sprites.append(mouth)
    
    # Create spritesheet
    sheet = Image.new('RGBA', (1120, 120), (0, 0, 0, 0))
    for i, sprite in enumerate(sprites):
        sheet.paste(sprite, (i * 160, 0))
    
    sheet_path = os.path.join(output_dir, 'mouth_sprites.png')
    sheet.save(sheet_path, 'PNG', optimize=True)
    print(f"✓ Saved: {sheet_path}")

def create_mouth_mask(output_path, size=(160, 120)):
    """Create soft mouth mask"""
    print("Creating mouth mask...")
    
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    
    # Draw ellipse with some margin
    draw.ellipse([10, 20, 150, 100], fill=255)
    
    # Apply strong blur for feathering
    mask = mask.filter(ImageFilter.GaussianBlur(12))
    
    mask.save(output_path, 'PNG', optimize=True)
    print(f"✓ Saved: {output_path}")

def extract_eyes_region(source_img, eyes_bbox, output_path, size=(232, 80)):
    """Extract and process eyes region"""
    print("Extracting eyes region...")
    
    # Crop eyes area
    eyes = source_img.crop(eyes_bbox)
    eyes = eyes.resize(size, Image.LANCZOS)
    
    # Enhance
    enhancer = ImageEnhance.Contrast(eyes)
    eyes = enhancer.enhance(1.1)
    
    if eyes.mode != 'RGBA':
        eyes = eyes.convert('RGBA')
    
    eyes.save(output_path, 'PNG', optimize=True)
    print(f"✓ Saved: {output_path}")
    return eyes

def create_eye_states(base_eyes, output_dir):
    """Create eye blink states"""
    print("Creating eye states...")
    
    # Open state (use base)
    open_path = os.path.join(output_dir, 'eyes_open.png')
    base_eyes.save(open_path, 'PNG', optimize=True)
    print(f"✓ Saved: {open_path}")
    
    # Half-closed (crop and squish)
    half = base_eyes.copy()
    half = half.resize((232, 40), Image.LANCZOS)
    temp = Image.new('RGBA', (232, 80), (0, 0, 0, 0))
    temp.paste(half, (0, 20))
    half_path = os.path.join(output_dir, 'eyes_half.png')
    temp.save(half_path, 'PNG', optimize=True)
    print(f"✓ Saved: {half_path}")
    
    # Closed (very thin line)
    closed = Image.new('RGBA', (232, 80), (0, 0, 0, 0))
    draw = ImageDraw.Draw(closed)
    # Sample color from base eyes for eyelid
    sample_color = base_eyes.getpixel((116, 5))
    draw.line([(10, 40), (110, 40)], fill=sample_color, width=3)
    draw.line([(122, 40), (222, 40)], fill=sample_color, width=3)
    closed = closed.filter(ImageFilter.GaussianBlur(1))
    closed_path = os.path.join(output_dir, 'eyes_closed.png')
    closed.save(closed_path, 'PNG', optimize=True)
    print(f"✓ Saved: {closed_path}")

def create_eyes_mask(output_path, size=(232, 80)):
    """Create soft eyes mask"""
    print("Creating eyes mask...")
    
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    
    # Two ellipses for left and right eye
    draw.ellipse([8, 10, 108, 70], fill=255)
    draw.ellipse([124, 10, 224, 70], fill=255)
    
    # Apply blur for feathering
    mask = mask.filter(ImageFilter.GaussianBlur(8))
    
    mask.save(output_path, 'PNG', optimize=True)
    print(f"✓ Saved: {output_path}")

def create_manifest(output_dir, avatar_name):
    """Create manifest.json"""
    import json
    
    manifest = {
        "id": avatar_name,
        "displayName": avatar_name.replace('_', ' ').title(),
        "version": "1.0.0",
        "description": "Avatar created from source photo",
        "base": {
            "type": "image",
            "src": "base_face.png",
            "width": 512,
            "height": 640
        },
        "mouth": {
            "spritesheet": "mouth_sprites.png",
            "mask": "mouth_mask.png",
            "frameWidth": 160,
            "frameHeight": 120,
            "visemes": ["REST", "AA", "EE", "OH", "OO", "FF", "TH"],
            "anchor": {
                "x": 176,
                "y": 400,
                "w": 160,
                "h": 120
            },
            "featherPx": 12,
            "blendMode": "normal"
        },
        "eyes": {
            "frames": {
                "open": "eyes_open.png",
                "half": "eyes_half.png",
                "closed": "eyes_closed.png"
            },
            "mask": "eyes_mask.png",
            "anchor": {
                "x": 140,
                "y": 240,
                "w": 232,
                "h": 80
            },
            "pupil": {
                "enabled": True,
                "maxOffsetX": 8,
                "maxOffsetY": 6
            },
            "featherPx": 8,
            "blendMode": "normal"
        },
        "mapping": {
            "REST": "REST",
            "AA": "AA",
            "EE": "EE",
            "OH": "OH",
            "OO": "OO",
            "FF": "FF",
            "TH": "TH"
        },
        "microMotion": {
            "enabled": True,
            "headBobAmplitude": 2,
            "headBobFrequency": 0.5,
            "headTiltAmplitude": 0.8,
            "breathingScale": 0.003,
            "breathingFrequency": 0.25
        }
    }
    
    manifest_path = os.path.join(output_dir, 'manifest.json')
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"✓ Saved: {manifest_path}")

def main():
    parser = argparse.ArgumentParser(description='Create avatar pack from source photo')
    parser.add_argument('source', help='Source face photo (JPG/PNG)')
    parser.add_argument('output_dir', help='Output directory for avatar pack')
    parser.add_argument('--name', default='custom_avatar', help='Avatar name')
    parser.add_argument('--mouth-bbox', default='170,390,342,510', 
                       help='Mouth bounding box: x1,y1,x2,y2')
    parser.add_argument('--eyes-bbox', default='130,220,382,300',
                       help='Eyes bounding box: x1,y1,x2,y2')
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Load source image
    print(f"\nLoading source image: {args.source}")
    source = Image.open(args.source)
    print(f"Source size: {source.size}")
    
    # Parse bounding boxes
    mouth_bbox = tuple(map(int, args.mouth_bbox.split(',')))
    eyes_bbox = tuple(map(int, args.eyes_bbox.split(',')))
    
    print(f"\nMouth region: {mouth_bbox}")
    print(f"Eyes region: {eyes_bbox}")
    print("\nProcessing...\n")
    
    # Create assets
    base_face = create_base_face(source, os.path.join(args.output_dir, 'base_face.png'))
    
    mouth = extract_mouth_region(source, mouth_bbox, 
                                 os.path.join(args.output_dir, 'mouth_base.png'))
    create_mouth_variations(mouth, args.output_dir)
    create_mouth_mask(os.path.join(args.output_dir, 'mouth_mask.png'))
    
    eyes = extract_eyes_region(source, eyes_bbox,
                               os.path.join(args.output_dir, 'eyes_base.png'))
    create_eye_states(eyes, args.output_dir)
    create_eyes_mask(os.path.join(args.output_dir, 'eyes_mask.png'))
    
    create_manifest(args.output_dir, args.name)
    
    print("\n" + "="*60)
    print("✅ Avatar pack created successfully!")
    print("="*60)
    print(f"\nNext steps:")
    print(f"1. Review assets in: {args.output_dir}")
    print(f"2. Copy to: web-demo/avatars/{args.name}/")
    print(f"3. Add avatar to dropdown in demo.js")
    print(f"4. Load in browser and use Calibration Mode to adjust anchors")
    print(f"5. Update manifest.json with final anchor values")
    print("\nFor better results:")
    print("- Use high-resolution source photo (1024x1280+)")
    print("- Ensure good lighting and front-facing pose")
    print("- Adjust bounding boxes with --mouth-bbox and --eyes-bbox")
    print("- Extract actual viseme photos from video for best quality")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Avatar Pack Creator")
        print("=" * 60)
        print("\nQuick start:")
        print("  python3 create_avatar_from_photo.py face.jpg output_avatar/")
        print("\nFor help:")
        print("  python3 create_avatar_from_photo.py --help")
        sys.exit(0)
    
    main()
