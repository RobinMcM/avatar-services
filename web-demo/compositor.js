/**
 * Photoreal Avatar Compositor
 * Handles loading, rendering, and animating photoreal 2D avatars with composited layers
 */

class AvatarCompositor {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.manifest = null;
        this.assets = {};
        this.loaded = false;
        this.calibrationMode = false;
        this.selectedAnchor = 'mouth'; // 'mouth' or 'eyes'
        
        // Animation state
        this.currentViseme = 'REST';
        this.targetViseme = 'REST';
        this.visemeBlend = 0;
        this.visemeTransitionSpeed = 0.15;
        
        this.eyeOpenness = 1.0;
        this.targetEyeOpenness = 1.0;
        this.eyePupilOffsetX = 0;
        this.eyePupilOffsetY = 0;
        this.targetPupilOffsetX = 0;
        this.targetPupilOffsetY = 0;
        
        // Micro-motion state
        this.microMotionTime = 0;
        this.headBobOffset = { x: 0, y: 0 };
        this.headTiltAngle = 0;
        this.breathingScale = 1.0;
        
        // Calibration adjustments (persisted in localStorage)
        this.anchorAdjustments = this.loadAnchorAdjustments();
    }
    
    /**
     * Load avatar manifest and assets
     */
    async loadAvatar(avatarId) {
        try {
            const basePath = `./avatars/${avatarId}`;
            
            // Load manifest
            const manifestResponse = await fetch(`${basePath}/manifest.json`);
            if (!manifestResponse.ok) {
                throw new Error(`Failed to load manifest for ${avatarId}`);
            }
            this.manifest = await manifestResponse.json();
            
            // Load all assets
            const assets = {};
            
            // Base face
            assets.baseFace = await this.loadImage(`${basePath}/${this.manifest.base.src}`);
            
            // Mouth assets
            assets.mouthSheet = await this.loadImage(`${basePath}/${this.manifest.mouth.spritesheet}`);
            assets.mouthMask = await this.loadImage(`${basePath}/${this.manifest.mouth.mask}`);
            
            // Eye assets
            assets.eyeOpen = await this.loadImage(`${basePath}/${this.manifest.eyes.frames.open}`);
            assets.eyeHalf = await this.loadImage(`${basePath}/${this.manifest.eyes.frames.half}`);
            assets.eyeClosed = await this.loadImage(`${basePath}/${this.manifest.eyes.frames.closed}`);
            assets.eyesMask = await this.loadImage(`${basePath}/${this.manifest.eyes.mask}`);
            
            this.assets = assets;
            this.loaded = true;
            
            console.log(`✓ Avatar ${avatarId} loaded successfully`);
            return true;
        } catch (error) {
            console.error('Failed to load avatar:', error);
            this.loaded = false;
            return false;
        }
    }
    
    /**
     * Load an image and return a promise
     */
    loadImage(src) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.crossOrigin = 'anonymous';
            img.onload = () => resolve(img);
            img.onerror = () => reject(new Error(`Failed to load image: ${src}`));
            img.src = src;
        });
    }
    
    /**
     * Update animation state based on timeline
     */
    update(currentTimeMs, mouthCues, eyeEvents, deltaTime) {
        if (!this.loaded) return;
        
        // Update target viseme from mouth cues
        this.updateMouthState(currentTimeMs, mouthCues);
        
        // Update eye state from eye events
        this.updateEyeState(currentTimeMs, eyeEvents);
        
        // Smooth interpolation
        this.interpolateViseme();
        this.interpolateEyes();
        
        // Micro-motion (idle animations)
        if (this.manifest.microMotion && this.manifest.microMotion.enabled) {
            this.updateMicroMotion(deltaTime);
        }
    }
    
    /**
     * Update mouth animation state
     */
    updateMouthState(currentTimeMs, mouthCues) {
        if (!mouthCues || mouthCues.length === 0) {
            this.targetViseme = 'REST';
            return;
        }
        
        // Find current cue
        let currentCue = null;
        for (const cue of mouthCues) {
            if (cue.t_ms <= currentTimeMs) {
                currentCue = cue;
            } else {
                break;
            }
        }
        
        if (currentCue) {
            const mappedViseme = this.manifest.mapping[currentCue.viseme] || currentCue.viseme;
            this.targetViseme = mappedViseme;
        }
    }
    
    /**
     * Update eye animation state
     */
    updateEyeState(currentTimeMs, eyeEvents) {
        if (!eyeEvents || eyeEvents.length === 0) {
            this.targetEyeOpenness = 1.0;
            this.targetPupilOffsetX = 0;
            this.targetPupilOffsetY = 0;
            return;
        }
        
        // Default to open
        this.targetEyeOpenness = 1.0;
        this.targetPupilOffsetX = 0;
        this.targetPupilOffsetY = 0;
        
        // Check for active events
        for (const event of eyeEvents) {
            const eventEnd = event.t_ms + event.duration_ms;
            
            if (currentTimeMs >= event.t_ms && currentTimeMs <= eventEnd) {
                const progress = (currentTimeMs - event.t_ms) / event.duration_ms;
                
                if (event.event_type === 'blink') {
                    // Blink animation: close then open
                    if (progress < 0.5) {
                        this.targetEyeOpenness = 1.0 - (progress * 2);
                    } else {
                        this.targetEyeOpenness = (progress - 0.5) * 2;
                    }
                } else if (event.event_type === 'saccade' && this.manifest.eyes.pupil && this.manifest.eyes.pupil.enabled) {
                    // Saccade (eye movement)
                    const maxOffsetX = this.manifest.eyes.pupil.maxOffsetX || 8;
                    const maxOffsetY = this.manifest.eyes.pupil.maxOffsetY || 6;
                    const magnitude = Math.sin(progress * Math.PI);
                    
                    switch (event.direction) {
                        case 'left':
                            this.targetPupilOffsetX = -maxOffsetX * magnitude;
                            break;
                        case 'right':
                            this.targetPupilOffsetX = maxOffsetX * magnitude;
                            break;
                        case 'up':
                            this.targetPupilOffsetY = -maxOffsetY * magnitude;
                            break;
                        case 'down':
                            this.targetPupilOffsetY = maxOffsetY * magnitude;
                            break;
                        default:
                            this.targetPupilOffsetX = maxOffsetX * 0.5 * magnitude;
                            break;
                    }
                }
            }
        }
    }
    
    /**
     * Smooth viseme interpolation
     */
    interpolateViseme() {
        if (this.currentViseme !== this.targetViseme) {
            this.visemeBlend += this.visemeTransitionSpeed;
            if (this.visemeBlend >= 1.0) {
                this.visemeBlend = 0;
                this.currentViseme = this.targetViseme;
            }
        } else {
            this.visemeBlend = 0;
        }
    }
    
    /**
     * Smooth eye interpolation
     */
    interpolateEyes() {
        const eyeSmoothing = 0.25;
        const pupilSmoothing = 0.2;
        
        this.eyeOpenness += (this.targetEyeOpenness - this.eyeOpenness) * eyeSmoothing;
        this.eyePupilOffsetX += (this.targetPupilOffsetX - this.eyePupilOffsetX) * pupilSmoothing;
        this.eyePupilOffsetY += (this.targetPupilOffsetY - this.eyePupilOffsetY) * pupilSmoothing;
    }
    
    /**
     * Update micro-motion (subtle idle animations)
     */
    updateMicroMotion(deltaTime) {
        this.microMotionTime += deltaTime;
        
        const mm = this.manifest.microMotion;
        
        // Head bob (gentle up/down motion)
        this.headBobOffset.y = Math.sin(this.microMotionTime * mm.headBobFrequency * 2 * Math.PI) * mm.headBobAmplitude;
        this.headBobOffset.x = Math.cos(this.microMotionTime * mm.headBobFrequency * Math.PI) * (mm.headBobAmplitude * 0.5);
        
        // Head tilt (slight rotation)
        this.headTiltAngle = Math.sin(this.microMotionTime * mm.headBobFrequency * Math.PI * 0.7) * mm.headTiltAmplitude * (Math.PI / 180);
        
        // Breathing (subtle scale)
        this.breathingScale = 1.0 + Math.sin(this.microMotionTime * mm.breathingFrequency * 2 * Math.PI) * mm.breathingScale;
    }
    
    /**
     * Render the avatar
     */
    render() {
        if (!this.loaded) {
            this.renderPlaceholder();
            return;
        }
        
        const ctx = this.ctx;
        const w = this.canvas.width;
        const h = this.canvas.height;
        
        // Clear
        ctx.clearRect(0, 0, w, h);
        
        // Apply micro-motion transformations
        ctx.save();
        ctx.translate(w / 2, h / 2);
        ctx.translate(this.headBobOffset.x, this.headBobOffset.y);
        ctx.rotate(this.headTiltAngle);
        ctx.scale(this.breathingScale, this.breathingScale);
        ctx.translate(-w / 2, -h / 2);
        
        // Draw base face
        this.drawBaseFace(ctx, w, h);
        
        // Draw eyes layer
        this.drawEyes(ctx, w, h);
        
        // Draw mouth layer
        this.drawMouth(ctx, w, h);
        
        ctx.restore();
        
        // Draw calibration overlay if enabled
        if (this.calibrationMode) {
            this.renderCalibrationOverlay(ctx, w, h);
        }
    }
    
    /**
     * Draw base face
     */
    drawBaseFace(ctx, canvasWidth, canvasHeight) {
        const img = this.assets.baseFace;
        const scale = Math.min(canvasWidth / img.width, canvasHeight / img.height);
        const scaledWidth = img.width * scale;
        const scaledHeight = img.height * scale;
        const x = (canvasWidth - scaledWidth) / 2;
        const y = (canvasHeight - scaledHeight) / 2;
        
        ctx.drawImage(img, x, y, scaledWidth, scaledHeight);
    }
    
    /**
     * Draw eyes with blinking
     */
    drawEyes(ctx, canvasWidth, canvasHeight) {
        // Select eye frame based on openness
        let eyeFrame;
        if (this.eyeOpenness > 0.66) {
            eyeFrame = this.assets.eyeOpen;
        } else if (this.eyeOpenness > 0.33) {
            eyeFrame = this.assets.eyeHalf;
        } else {
            eyeFrame = this.assets.eyeClosed;
        }
        
        const anchor = this.getAdjustedAnchor('eyes');
        const scale = this.getScale(canvasWidth, canvasHeight);
        
        const x = anchor.x * scale + (canvasWidth - this.manifest.base.width * scale) / 2;
        const y = anchor.y * scale + (canvasHeight - this.manifest.base.height * scale) / 2;
        const w = anchor.w * scale;
        const h = anchor.h * scale;
        
        // Apply pupil offset if applicable
        const offsetX = this.eyePupilOffsetX * scale;
        const offsetY = this.eyePupilOffsetY * scale;
        
        // Composite with mask
        this.compositeMasked(ctx, eyeFrame, this.assets.eyesMask, x + offsetX, y + offsetY, w, h);
    }
    
    /**
     * Draw mouth from spritesheet
     */
    drawMouth(ctx, canvasWidth, canvasHeight) {
        const visemeIndex = this.manifest.mouth.visemes.indexOf(this.currentViseme);
        if (visemeIndex === -1) return;
        
        const anchor = this.getAdjustedAnchor('mouth');
        const scale = this.getScale(canvasWidth, canvasHeight);
        
        const x = anchor.x * scale + (canvasWidth - this.manifest.base.width * scale) / 2;
        const y = anchor.y * scale + (canvasHeight - this.manifest.base.height * scale) / 2;
        const w = anchor.w * scale;
        const h = anchor.h * scale;
        
        // Extract frame from spritesheet
        const frameWidth = this.manifest.mouth.frameWidth;
        const frameHeight = this.manifest.mouth.frameHeight;
        const sx = visemeIndex * frameWidth;
        
        // Create temporary canvas for frame
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = frameWidth;
        tempCanvas.height = frameHeight;
        const tempCtx = tempCanvas.getContext('2d');
        tempCtx.drawImage(this.assets.mouthSheet, sx, 0, frameWidth, frameHeight, 0, 0, frameWidth, frameHeight);
        
        // Composite with mask
        this.compositeMasked(ctx, tempCanvas, this.assets.mouthMask, x, y, w, h);
        
        // If blending between visemes, draw next frame with reduced opacity
        if (this.visemeBlend > 0 && this.currentViseme !== this.targetViseme) {
            const nextVisemeIndex = this.manifest.mouth.visemes.indexOf(this.targetViseme);
            if (nextVisemeIndex !== -1) {
                const nextCanvas = document.createElement('canvas');
                nextCanvas.width = frameWidth;
                nextCanvas.height = frameHeight;
                const nextCtx = nextCanvas.getContext('2d');
                nextCtx.drawImage(this.assets.mouthSheet, nextVisemeIndex * frameWidth, 0, frameWidth, frameHeight, 0, 0, frameWidth, frameHeight);
                
                ctx.save();
                ctx.globalAlpha = this.visemeBlend;
                this.compositeMasked(ctx, nextCanvas, this.assets.mouthMask, x, y, w, h);
                ctx.restore();
            }
        }
    }
    
    /**
     * Composite an image with a mask
     */
    compositeMasked(ctx, sourceImage, maskImage, x, y, w, h) {
        // Create temporary canvas for masked composite
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = w;
        tempCanvas.height = h;
        const tempCtx = tempCanvas.getContext('2d');
        
        // Draw source image
        tempCtx.drawImage(sourceImage, 0, 0, w, h);
        
        // Apply mask using destination-in
        tempCtx.globalCompositeOperation = 'destination-in';
        tempCtx.drawImage(maskImage, 0, 0, w, h);
        
        // Draw to main canvas
        ctx.drawImage(tempCanvas, x, y);
    }
    
    /**
     * Get scale factor for current canvas size
     */
    getScale(canvasWidth, canvasHeight) {
        return Math.min(canvasWidth / this.manifest.base.width, canvasHeight / this.manifest.base.height);
    }
    
    /**
     * Get anchor with calibration adjustments
     */
    getAdjustedAnchor(type) {
        const anchor = { ...this.manifest[type].anchor };
        const adjustments = this.anchorAdjustments[this.manifest.id] || {};
        const typeAdj = adjustments[type] || { x: 0, y: 0, w: 0, h: 0 };
        
        return {
            x: anchor.x + typeAdj.x,
            y: anchor.y + typeAdj.y,
            w: anchor.w + typeAdj.w,
            h: anchor.h + typeAdj.h
        };
    }
    
    /**
     * Render calibration overlay
     */
    renderCalibrationOverlay(ctx, w, h) {
        const scale = this.getScale(w, h);
        const offsetX = (w - this.manifest.base.width * scale) / 2;
        const offsetY = (h - this.manifest.base.height * scale) / 2;
        
        ctx.save();
        ctx.strokeStyle = this.selectedAnchor === 'mouth' ? '#00ff00' : '#ffff00';
        ctx.lineWidth = 2;
        
        const mouthAnchor = this.getAdjustedAnchor('mouth');
        ctx.strokeRect(
            mouthAnchor.x * scale + offsetX,
            mouthAnchor.y * scale + offsetY,
            mouthAnchor.w * scale,
            mouthAnchor.h * scale
        );
        
        ctx.strokeStyle = this.selectedAnchor === 'eyes' ? '#00ff00' : '#00ffff';
        const eyesAnchor = this.getAdjustedAnchor('eyes');
        ctx.strokeRect(
            eyesAnchor.x * scale + offsetX,
            eyesAnchor.y * scale + offsetY,
            eyesAnchor.w * scale,
            eyesAnchor.h * scale
        );
        
        // Draw info
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        ctx.fillRect(5, 5, 300, 80);
        ctx.fillStyle = '#00ff00';
        ctx.font = '12px monospace';
        ctx.fillText(`Calibration Mode: ${this.selectedAnchor}`, 10, 20);
        ctx.fillText(`Arrows: move | Shift+Arrows: resize`, 10, 35);
        ctx.fillText(`Tab: switch anchor | C: toggle calibration`, 10, 50);
        ctx.fillText(`Mouth: ${mouthAnchor.x},${mouthAnchor.y} ${mouthAnchor.w}x${mouthAnchor.h}`, 10, 65);
        ctx.fillText(`Eyes:  ${eyesAnchor.x},${eyesAnchor.y} ${eyesAnchor.w}x${eyesAnchor.h}`, 10, 80);
        
        ctx.restore();
    }
    
    /**
     * Render placeholder when no avatar loaded
     */
    renderPlaceholder() {
        const ctx = this.ctx;
        const w = this.canvas.width;
        const h = this.canvas.height;
        
        ctx.fillStyle = '#1a1a25';
        ctx.fillRect(0, 0, w, h);
        
        ctx.fillStyle = '#6366f1';
        ctx.font = '16px Outfit, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Loading avatar...', w / 2, h / 2);
    }
    
    /**
     * Calibration controls
     */
    adjustAnchor(dx, dy, dw, dh) {
        if (!this.manifest) return;
        
        const avatarId = this.manifest.id;
        if (!this.anchorAdjustments[avatarId]) {
            this.anchorAdjustments[avatarId] = { mouth: { x: 0, y: 0, w: 0, h: 0 }, eyes: { x: 0, y: 0, w: 0, h: 0 } };
        }
        
        const adj = this.anchorAdjustments[avatarId][this.selectedAnchor];
        adj.x += dx;
        adj.y += dy;
        adj.w += dw;
        adj.h += dh;
        
        this.saveAnchorAdjustments();
    }
    
    /**
     * Load anchor adjustments from localStorage
     */
    loadAnchorAdjustments() {
        try {
            const saved = localStorage.getItem('avatarAnchorAdjustments');
            return saved ? JSON.parse(saved) : {};
        } catch {
            return {};
        }
    }
    
    /**
     * Save anchor adjustments to localStorage
     */
    saveAnchorAdjustments() {
        try {
            localStorage.setItem('avatarAnchorAdjustments', JSON.stringify(this.anchorAdjustments));
        } catch (e) {
            console.warn('Failed to save anchor adjustments:', e);
        }
    }
    
    /**
     * Toggle calibration mode
     */
    toggleCalibration() {
        this.calibrationMode = !this.calibrationMode;
        return this.calibrationMode;
    }
    
    /**
     * Switch selected anchor
     */
    switchAnchor() {
        this.selectedAnchor = this.selectedAnchor === 'mouth' ? 'eyes' : 'mouth';
    }
    
    /**
     * Reset animation state
     */
    reset() {
        this.currentViseme = 'REST';
        this.targetViseme = 'REST';
        this.visemeBlend = 0;
        this.eyeOpenness = 1.0;
        this.targetEyeOpenness = 1.0;
        this.eyePupilOffsetX = 0;
        this.eyePupilOffsetY = 0;
        this.microMotionTime = 0;
    }
}
