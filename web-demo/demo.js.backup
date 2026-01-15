/**
 * Avatar Service Demo
 * Canvas-based 2D avatar with TTS and lip-sync animation
 */

// Configuration
const API_BASE_URL = window.location.origin;
const API_ENDPOINT = `${API_BASE_URL}/v1/avatar/render`;

// DOM Elements
const canvas = document.getElementById('avatar-canvas');
const ctx = canvas.getContext('2d');
const textInput = document.getElementById('text-input');
const voiceSelect = document.getElementById('voice-select');
const speedSlider = document.getElementById('speed-slider');
const speedValue = document.getElementById('speed-value');
const renderBtn = document.getElementById('render-btn');
const renderBtnText = document.getElementById('render-btn-text');
const stopBtn = document.getElementById('stop-btn');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const responseJson = document.getElementById('response-json');
const responseMeta = document.getElementById('response-meta');
const timelinePanel = document.getElementById('timeline-panel');
const mouthTimeline = document.getElementById('mouth-timeline');
const eyeTimeline = document.getElementById('eye-timeline');
const mouthPlayhead = document.getElementById('mouth-playhead');
const eyePlayhead = document.getElementById('eye-playhead');

// Audio
let audio = null;
let audioContext = null;

// Animation state
let animationState = {
    isPlaying: false,
    startTime: 0,
    mouthCues: [],
    eyeEvents: [],
    durationMs: 0,
    currentViseme: 'REST',
    targetViseme: 'REST',
    visemeWeight: 0,
    eyeOpenness: 1,
    eyeTargetOpenness: 1,
    eyeOffsetX: 0,
    eyeOffsetY: 0,
    eyeTargetOffsetX: 0,
    eyeTargetOffsetY: 0,
};

// Viseme definitions - mouth shapes
const visemes = {
    REST: { mouthWidth: 0.4, mouthHeight: 0.05, lipRound: 0, jawOpen: 0 },
    AA: { mouthWidth: 0.5, mouthHeight: 0.4, lipRound: 0, jawOpen: 0.6 },
    EE: { mouthWidth: 0.55, mouthHeight: 0.15, lipRound: 0, jawOpen: 0.15 },
    OH: { mouthWidth: 0.35, mouthHeight: 0.35, lipRound: 0.5, jawOpen: 0.4 },
    OO: { mouthWidth: 0.25, mouthHeight: 0.25, lipRound: 0.8, jawOpen: 0.2 },
    FF: { mouthWidth: 0.5, mouthHeight: 0.08, lipRound: 0, jawOpen: 0.05 },
    TH: { mouthWidth: 0.45, mouthHeight: 0.12, lipRound: 0, jawOpen: 0.1 },
};

// Colors for the avatar
const colors = {
    skin: '#f5d0c5',
    skinShadow: '#e8b4a6',
    hair: '#2d1810',
    hairHighlight: '#4a2820',
    eye: '#3d5a80',
    eyeWhite: '#f8f8f8',
    eyePupil: '#1a1a2e',
    eyebrow: '#2d1810',
    lipOuter: '#c77b7b',
    lipInner: '#a85555',
    teeth: '#f5f5f5',
    tongue: '#d4777a',
    background: '#1a1a25',
};

// Speed slider event
speedSlider.addEventListener('input', () => {
    speedValue.textContent = `${speedSlider.value}x`;
});

// Render button event
renderBtn.addEventListener('click', handleRender);

// Stop button event
stopBtn.addEventListener('click', handleStop);

/**
 * Handle render button click
 */
async function handleRender() {
    const text = textInput.value.trim();
    if (!text) {
        setStatus('error', 'Please enter some text');
        return;
    }

    setStatus('processing', 'Generating...');
    setButtonLoading(true);

    try {
        const response = await fetch(API_ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                text: text,
                voice_id: voiceSelect.value,
                speed: parseFloat(speedSlider.value),
            }),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || data.error || 'Request failed');
        }

        displayResponse(data);

        if (data.status === 'completed') {
            await playAnimation(data);
        } else {
            throw new Error(`Render failed: ${data.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Render error:', error);
        setStatus('error', error.message);
        displayError(error.message);
    } finally {
        setButtonLoading(false);
    }
}

/**
 * Handle stop button click
 */
function handleStop() {
    if (audio) {
        audio.pause();
        audio.currentTime = 0;
    }
    animationState.isPlaying = false;
    setStatus('ready', 'Stopped');
    resetAvatar();
}

/**
 * Set status indicator
 */
function setStatus(state, message) {
    statusDot.className = 'status-dot';
    if (state === 'processing') {
        statusDot.classList.add('processing');
    } else if (state === 'active') {
        statusDot.classList.add('active');
    }
    statusText.textContent = message;
}

/**
 * Set button loading state
 */
function setButtonLoading(loading) {
    renderBtn.disabled = loading;
    if (loading) {
        renderBtnText.innerHTML = '<span class="spinner"></span> Processing...';
    } else {
        renderBtnText.textContent = 'Generate & Play';
    }
}

/**
 * Display API response with syntax highlighting
 */
function displayResponse(data) {
    const formatted = JSON.stringify(data, null, 2);
    const highlighted = formatted
        .replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:')
        .replace(/: "([^"]*)"([,\n])/g, ': <span class="json-string">"$1"</span>$2')
        .replace(/: (-?\d+\.?\d*)([,\n])/g, ': <span class="json-number">$1</span>$2')
        .replace(/: (true|false)([,\n])/g, ': <span class="json-boolean">$1</span>$2');
    
    responseJson.innerHTML = highlighted;

    // Update meta info
    const cached = data.cached ? ' (cached)' : '';
    const duration = data.duration_ms ? `${(data.duration_ms / 1000).toFixed(2)}s` : 'N/A';
    const processingTime = data.processing_time_ms ? `${data.processing_time_ms}ms` : 'N/A';
    responseMeta.textContent = `Duration: ${duration} | Processing: ${processingTime}${cached}`;

    // Display timeline
    if (data.mouth_cues && data.eye_events && data.duration_ms) {
        displayTimeline(data.mouth_cues, data.eye_events, data.duration_ms);
    }
}

/**
 * Display error in response panel
 */
function displayError(message) {
    responseJson.innerHTML = `<span style="color: var(--error)">Error: ${message}</span>`;
    responseMeta.textContent = '';
}

/**
 * Display animation timeline
 */
function displayTimeline(mouthCues, eyeEvents, durationMs) {
    timelinePanel.style.display = 'block';

    // Clear existing markers (except playhead)
    mouthTimeline.querySelectorAll('.timeline-marker').forEach(el => el.remove());
    eyeTimeline.querySelectorAll('.timeline-marker').forEach(el => el.remove());

    // Viseme colors
    const visemeColors = {
        REST: '#6b7280',
        AA: '#ef4444',
        EE: '#f59e0b',
        OH: '#22c55e',
        OO: '#3b82f6',
        FF: '#8b5cf6',
        TH: '#ec4899',
    };

    // Add mouth cue markers
    mouthCues.forEach((cue, i) => {
        const nextCue = mouthCues[i + 1];
        const startPercent = (cue.t_ms / durationMs) * 100;
        const endMs = nextCue ? nextCue.t_ms : durationMs;
        const widthPercent = ((endMs - cue.t_ms) / durationMs) * 100;

        const marker = document.createElement('div');
        marker.className = 'timeline-marker';
        marker.style.left = `${startPercent}%`;
        marker.style.width = `${Math.max(widthPercent, 0.5)}%`;
        marker.style.background = visemeColors[cue.viseme] || '#6b7280';
        marker.style.opacity = cue.weight;
        marker.title = `${cue.viseme} @ ${cue.t_ms}ms`;
        mouthTimeline.appendChild(marker);
    });

    // Eye event colors
    const eyeEventColors = {
        blink: '#fbbf24',
        saccade: '#60a5fa',
    };

    // Add eye event markers
    eyeEvents.forEach(event => {
        const startPercent = (event.t_ms / durationMs) * 100;
        const widthPercent = (event.duration_ms / durationMs) * 100;

        const marker = document.createElement('div');
        marker.className = 'timeline-marker';
        marker.style.left = `${startPercent}%`;
        marker.style.width = `${Math.max(widthPercent, 0.5)}%`;
        marker.style.background = eyeEventColors[event.event_type] || '#6b7280';
        marker.title = `${event.event_type} @ ${event.t_ms}ms`;
        eyeTimeline.appendChild(marker);
    });
}

/**
 * Play audio and animation
 */
async function playAnimation(data) {
    // Stop any existing playback
    handleStop();

    // Set up animation state
    animationState.mouthCues = data.mouth_cues || [];
    animationState.eyeEvents = data.eye_events || [];
    animationState.durationMs = data.duration_ms || 0;
    animationState.currentViseme = 'REST';
    animationState.targetViseme = 'REST';
    animationState.visemeWeight = 0;
    animationState.eyeOpenness = 1;
    animationState.eyeTargetOpenness = 1;

    // Create audio element
    audio = new Audio(data.audio_url);
    audio.crossOrigin = 'anonymous';

    return new Promise((resolve, reject) => {
        audio.oncanplaythrough = () => {
            audio.play().then(() => {
                animationState.isPlaying = true;
                animationState.startTime = performance.now();
                setStatus('active', 'Playing...');
                requestAnimationFrame(animationLoop);
                resolve();
            }).catch(reject);
        };

        audio.onerror = () => {
            reject(new Error('Failed to load audio'));
        };

        audio.onended = () => {
            animationState.isPlaying = false;
            setStatus('ready', 'Playback complete');
            resetAvatar();
        };

        audio.load();
    });
}

/**
 * Main animation loop
 */
function animationLoop(timestamp) {
    if (!animationState.isPlaying) return;

    const currentTimeMs = audio ? audio.currentTime * 1000 : 0;

    // Update playhead positions
    if (animationState.durationMs > 0) {
        const percent = (currentTimeMs / animationState.durationMs) * 100;
        mouthPlayhead.style.left = `${Math.min(percent, 100)}%`;
        eyePlayhead.style.left = `${Math.min(percent, 100)}%`;
    }

    // Find current mouth cue
    updateMouthState(currentTimeMs);

    // Process eye events
    updateEyeState(currentTimeMs);

    // Render avatar
    renderAvatar();

    if (animationState.isPlaying) {
        requestAnimationFrame(animationLoop);
    }
}

/**
 * Update mouth animation state
 */
function updateMouthState(currentTimeMs) {
    const cues = animationState.mouthCues;
    
    // Find the current and next cue for interpolation
    let currentCue = null;
    let nextCue = null;

    for (let i = 0; i < cues.length; i++) {
        if (cues[i].t_ms <= currentTimeMs) {
            currentCue = cues[i];
            nextCue = cues[i + 1] || null;
        } else {
            break;
        }
    }

    if (currentCue) {
        animationState.targetViseme = currentCue.viseme;
        
        // Calculate interpolation weight
        if (nextCue) {
            const duration = nextCue.t_ms - currentCue.t_ms;
            const elapsed = currentTimeMs - currentCue.t_ms;
            animationState.visemeWeight = Math.min(elapsed / Math.max(duration * 0.3, 50), 1);
        } else {
            animationState.visemeWeight = 1;
        }
    }

    // Smooth interpolation between visemes
    if (animationState.currentViseme !== animationState.targetViseme) {
        animationState.currentViseme = animationState.targetViseme;
    }
}

/**
 * Update eye animation state
 */
function updateEyeState(currentTimeMs) {
    const events = animationState.eyeEvents;
    
    // Default state
    animationState.eyeTargetOpenness = 1;
    animationState.eyeTargetOffsetX = 0;
    animationState.eyeTargetOffsetY = 0;

    // Check active eye events
    for (const event of events) {
        const eventEnd = event.t_ms + event.duration_ms;
        
        if (currentTimeMs >= event.t_ms && currentTimeMs <= eventEnd) {
            const progress = (currentTimeMs - event.t_ms) / event.duration_ms;
            
            if (event.event_type === 'blink') {
                // Blink: close then open
                if (progress < 0.5) {
                    animationState.eyeTargetOpenness = 1 - (progress * 2);
                } else {
                    animationState.eyeTargetOpenness = (progress - 0.5) * 2;
                }
            } else if (event.event_type === 'saccade') {
                // Subtle eye movement
                const magnitude = 3;
                switch (event.direction) {
                    case 'left':
                        animationState.eyeTargetOffsetX = -magnitude * Math.sin(progress * Math.PI);
                        break;
                    case 'right':
                        animationState.eyeTargetOffsetX = magnitude * Math.sin(progress * Math.PI);
                        break;
                    case 'up':
                        animationState.eyeTargetOffsetY = -magnitude * Math.sin(progress * Math.PI);
                        break;
                    case 'down':
                        animationState.eyeTargetOffsetY = magnitude * Math.sin(progress * Math.PI);
                        break;
                    default:
                        // Random slight movement
                        animationState.eyeTargetOffsetX = magnitude * 0.5 * Math.sin(progress * Math.PI);
                }
            }
        }
    }

    // Smooth interpolation
    const smoothing = 0.3;
    animationState.eyeOpenness += (animationState.eyeTargetOpenness - animationState.eyeOpenness) * smoothing;
    animationState.eyeOffsetX += (animationState.eyeTargetOffsetX - animationState.eyeOffsetX) * smoothing;
    animationState.eyeOffsetY += (animationState.eyeTargetOffsetY - animationState.eyeOffsetY) * smoothing;
}

/**
 * Render avatar on canvas
 */
function renderAvatar() {
    const w = canvas.width;
    const h = canvas.height;
    const cx = w / 2;
    const cy = h / 2;

    // Clear canvas
    ctx.fillStyle = colors.background;
    ctx.fillRect(0, 0, w, h);

    // Get current mouth shape through interpolation
    const currentShape = visemes[animationState.currentViseme] || visemes.REST;
    const weight = animationState.visemeWeight;

    // Draw hair (back)
    ctx.fillStyle = colors.hair;
    ctx.beginPath();
    ctx.ellipse(cx, cy - 30, 130, 150, 0, Math.PI, 0);
    ctx.fill();

    // Draw neck
    ctx.fillStyle = colors.skinShadow;
    ctx.beginPath();
    ctx.moveTo(cx - 40, cy + 100);
    ctx.lineTo(cx - 50, cy + 180);
    ctx.lineTo(cx + 50, cy + 180);
    ctx.lineTo(cx + 40, cy + 100);
    ctx.closePath();
    ctx.fill();

    // Draw face shape
    ctx.fillStyle = colors.skin;
    ctx.beginPath();
    ctx.ellipse(cx, cy, 110, 130, 0, 0, Math.PI * 2);
    ctx.fill();

    // Face shadow
    const gradient = ctx.createRadialGradient(cx - 30, cy - 30, 0, cx, cy, 130);
    gradient.addColorStop(0, 'transparent');
    gradient.addColorStop(1, 'rgba(0,0,0,0.1)');
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw eyebrows
    ctx.strokeStyle = colors.eyebrow;
    ctx.lineWidth = 4;
    ctx.lineCap = 'round';

    // Left eyebrow
    ctx.beginPath();
    ctx.moveTo(cx - 65, cy - 55);
    ctx.quadraticCurveTo(cx - 45, cy - 65, cx - 25, cy - 55);
    ctx.stroke();

    // Right eyebrow
    ctx.beginPath();
    ctx.moveTo(cx + 25, cy - 55);
    ctx.quadraticCurveTo(cx + 45, cy - 65, cx + 65, cy - 55);
    ctx.stroke();

    // Draw eyes
    const eyeY = cy - 25;
    const eyeSpacing = 45;
    const eyeWidth = 25;
    const eyeHeight = 18 * animationState.eyeOpenness;

    // Left eye
    drawEye(cx - eyeSpacing + animationState.eyeOffsetX, eyeY + animationState.eyeOffsetY, eyeWidth, eyeHeight);
    
    // Right eye
    drawEye(cx + eyeSpacing + animationState.eyeOffsetX, eyeY + animationState.eyeOffsetY, eyeWidth, eyeHeight);

    // Draw nose
    ctx.strokeStyle = colors.skinShadow;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy - 10);
    ctx.quadraticCurveTo(cx + 8, cy + 20, cx, cy + 25);
    ctx.stroke();

    // Draw mouth based on current viseme
    drawMouth(cx, cy + 60, currentShape, weight);

    // Draw hair (front/bangs)
    ctx.fillStyle = colors.hair;
    ctx.beginPath();
    ctx.moveTo(cx - 100, cy - 80);
    ctx.quadraticCurveTo(cx - 60, cy - 140, cx, cy - 130);
    ctx.quadraticCurveTo(cx + 60, cy - 140, cx + 100, cy - 80);
    ctx.quadraticCurveTo(cx + 90, cy - 60, cx + 110, cy - 30);
    ctx.lineTo(cx + 115, cy - 50);
    ctx.quadraticCurveTo(cx + 80, cy - 90, cx, cy - 85);
    ctx.quadraticCurveTo(cx - 80, cy - 90, cx - 115, cy - 50);
    ctx.lineTo(cx - 110, cy - 30);
    ctx.quadraticCurveTo(cx - 90, cy - 60, cx - 100, cy - 80);
    ctx.closePath();
    ctx.fill();

    // Hair highlight
    ctx.fillStyle = colors.hairHighlight;
    ctx.beginPath();
    ctx.ellipse(cx - 40, cy - 100, 30, 20, -0.3, 0, Math.PI * 2);
    ctx.fill();
}

/**
 * Draw an eye
 */
function drawEye(x, y, width, height) {
    if (height < 2) {
        // Eye is nearly closed, just draw a line
        ctx.strokeStyle = colors.eyebrow;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x - width, y);
        ctx.lineTo(x + width, y);
        ctx.stroke();
        return;
    }

    // Eye white
    ctx.fillStyle = colors.eyeWhite;
    ctx.beginPath();
    ctx.ellipse(x, y, width, height, 0, 0, Math.PI * 2);
    ctx.fill();

    // Eye border
    ctx.strokeStyle = colors.skinShadow;
    ctx.lineWidth = 1;
    ctx.stroke();

    // Iris
    const irisRadius = Math.min(height * 0.7, 12);
    ctx.fillStyle = colors.eye;
    ctx.beginPath();
    ctx.arc(x + animationState.eyeOffsetX * 0.3, y + animationState.eyeOffsetY * 0.3, irisRadius, 0, Math.PI * 2);
    ctx.fill();

    // Pupil
    const pupilRadius = irisRadius * 0.5;
    ctx.fillStyle = colors.eyePupil;
    ctx.beginPath();
    ctx.arc(x + animationState.eyeOffsetX * 0.3, y + animationState.eyeOffsetY * 0.3, pupilRadius, 0, Math.PI * 2);
    ctx.fill();

    // Eye highlight
    ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
    ctx.beginPath();
    ctx.arc(x - 4 + animationState.eyeOffsetX * 0.2, y - 4 + animationState.eyeOffsetY * 0.2, 3, 0, Math.PI * 2);
    ctx.fill();
}

/**
 * Draw mouth based on viseme shape
 */
function drawMouth(x, y, shape, weight) {
    const baseWidth = 40;
    const baseHeight = 5;

    // Calculate animated values
    const mouthWidth = baseWidth * (0.8 + shape.mouthWidth * 0.5);
    const mouthHeight = baseHeight + shape.mouthHeight * 35;
    const lipRound = shape.lipRound;
    const jawOpen = shape.jawOpen;

    // Outer lip
    ctx.fillStyle = colors.lipOuter;
    ctx.beginPath();

    if (mouthHeight > 10) {
        // Open mouth
        ctx.ellipse(x, y + jawOpen * 10, mouthWidth, mouthHeight, 0, 0, Math.PI * 2);
        ctx.fill();

        // Inner mouth (dark)
        ctx.fillStyle = colors.lipInner;
        ctx.beginPath();
        ctx.ellipse(x, y + jawOpen * 10, mouthWidth * 0.85, mouthHeight * 0.7, 0, 0, Math.PI * 2);
        ctx.fill();

        // Teeth (top)
        if (mouthHeight > 15) {
            ctx.fillStyle = colors.teeth;
            ctx.beginPath();
            ctx.ellipse(x, y - 2 + jawOpen * 10, mouthWidth * 0.7, Math.min(mouthHeight * 0.3, 10), 0, Math.PI, 0);
            ctx.fill();
        }

        // Tongue hint
        if (mouthHeight > 20) {
            ctx.fillStyle = colors.tongue;
            ctx.beginPath();
            ctx.ellipse(x, y + mouthHeight * 0.4 + jawOpen * 10, mouthWidth * 0.5, mouthHeight * 0.25, 0, 0, Math.PI);
            ctx.fill();
        }
    } else {
        // Closed or nearly closed mouth
        ctx.moveTo(x - mouthWidth, y);
        
        if (lipRound > 0.3) {
            // Rounded lips (like 'O' or 'OO')
            ctx.ellipse(x, y, mouthWidth * (1 - lipRound * 0.5), mouthHeight + lipRound * 5, 0, 0, Math.PI * 2);
        } else {
            // Flat lips
            ctx.quadraticCurveTo(x, y + mouthHeight * 2, x + mouthWidth, y);
            ctx.quadraticCurveTo(x, y - mouthHeight, x - mouthWidth, y);
        }
        ctx.fill();
    }

    // Lip highlight
    ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
    ctx.beginPath();
    ctx.ellipse(x, y - mouthHeight * 0.3, mouthWidth * 0.5, 2, 0, 0, Math.PI * 2);
    ctx.fill();
}

/**
 * Reset avatar to neutral state
 */
function resetAvatar() {
    animationState.currentViseme = 'REST';
    animationState.targetViseme = 'REST';
    animationState.visemeWeight = 0;
    animationState.eyeOpenness = 1;
    animationState.eyeTargetOpenness = 1;
    animationState.eyeOffsetX = 0;
    animationState.eyeOffsetY = 0;
    
    mouthPlayhead.style.left = '0%';
    eyePlayhead.style.left = '0%';
    
    renderAvatar();
}

// Initial render
renderAvatar();

// Add idle animation (subtle breathing/blinking when not playing)
let idleAnimationId = null;

function startIdleAnimation() {
    if (idleAnimationId) return;
    
    let lastBlink = 0;
    let blinking = false;
    let blinkProgress = 0;

    function idleLoop(timestamp) {
        if (animationState.isPlaying) {
            idleAnimationId = null;
            return;
        }

        // Random blinking every 3-7 seconds
        if (!blinking && timestamp - lastBlink > 3000 + Math.random() * 4000) {
            blinking = true;
            blinkProgress = 0;
            lastBlink = timestamp;
        }

        if (blinking) {
            blinkProgress += 0.1;
            if (blinkProgress < 0.5) {
                animationState.eyeOpenness = 1 - blinkProgress * 2;
            } else if (blinkProgress < 1) {
                animationState.eyeOpenness = (blinkProgress - 0.5) * 2;
            } else {
                animationState.eyeOpenness = 1;
                blinking = false;
            }
        }

        renderAvatar();
        idleAnimationId = requestAnimationFrame(idleLoop);
    }

    idleAnimationId = requestAnimationFrame(idleLoop);
}

// Start idle animation on load
startIdleAnimation();

// Restart idle animation when playback stops
const originalHandleStop = handleStop;
handleStop = function() {
    originalHandleStop();
    setTimeout(startIdleAnimation, 100);
};
