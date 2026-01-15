/**
 * Avatar Service Demo - Photoreal Edition
 * Uses compositor.js for photoreal 2D avatar rendering
 */

// Configuration
const API_BASE_URL = window.location.origin;
const API_ENDPOINT = `${API_BASE_URL}/v1/avatar/render`;

// DOM Elements
const canvas = document.getElementById('avatar-canvas');
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

// Photoreal avatar controls
const avatarSelect = document.getElementById('avatar-select');
const calibrationToggle = document.getElementById('calibration-toggle');
const calibrationInfo = document.getElementById('calibration-info');

// Audio
let audio = null;

// Avatar compositor
let compositor = null;

// Animation state
let animationState = {
    isPlaying: false,
    startTime: 0,
    lastFrameTime: 0,
    mouthCues: [],
    eyeEvents: [],
    durationMs: 0,
};

// Initialize
async function init() {
    // Create compositor
    compositor = new AvatarCompositor(canvas);
    
    // Load available avatars
    await loadAvatarList();
    
    // Load default avatar
    const defaultAvatar = avatarSelect.value || 'realistic_female_v1';
    await loadAvatar(defaultAvatar);
    
    // Setup event listeners
    setupEventListeners();
    
    // Start render loop
    requestAnimationFrame(renderLoop);
    
    // Start idle animation
    startIdleAnimation();
}

/**
 * Load list of available avatars
 */
async function loadAvatarList() {
    // For now, hardcoded. Could be dynamic by scanning avatars/ directory
    const avatars = [
        { id: 'realistic_female_v1', name: 'Realistic Female v1' }
    ];
    
    avatarSelect.innerHTML = '';
    avatars.forEach(avatar => {
        const option = document.createElement('option');
        option.value = avatar.id;
        option.textContent = avatar.name;
        avatarSelect.appendChild(option);
    });
}

/**
 * Load an avatar
 */
async function loadAvatar(avatarId) {
    setStatus('processing', 'Loading avatar...');
    
    const success = await compositor.loadAvatar(avatarId);
    
    if (success) {
        setStatus('ready', 'Avatar loaded');
        compositor.render();
    } else {
        setStatus('error', 'Failed to load avatar');
    }
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Speed slider
    speedSlider.addEventListener('input', () => {
        speedValue.textContent = `${speedSlider.value}x`;
    });
    
    // Render button
    renderBtn.addEventListener('click', handleRender);
    
    // Stop button
    stopBtn.addEventListener('click', handleStop);
    
    // Avatar selection
    avatarSelect.addEventListener('change', async () => {
        await loadAvatar(avatarSelect.value);
    });
    
    // Calibration toggle
    calibrationToggle.addEventListener('change', () => {
        compositor.toggleCalibration();
        calibrationInfo.style.display = calibrationToggle.checked ? 'block' : 'none';
    });
    
    // Keyboard controls for calibration
    document.addEventListener('keydown', handleKeyboard);
}

/**
 * Handle keyboard input for calibration
 */
function handleKeyboard(e) {
    if (!compositor.calibrationMode) return;
    
    const step = e.shiftKey ? 5 : 1;
    const resizeStep = e.shiftKey ? 5 : 2;
    
    switch(e.key) {
        case 'ArrowLeft':
            e.preventDefault();
            compositor.adjustAnchor(e.shiftKey ? 0 : -step, 0, e.shiftKey ? -resizeStep : 0, 0);
            break;
        case 'ArrowRight':
            e.preventDefault();
            compositor.adjustAnchor(e.shiftKey ? 0 : step, 0, e.shiftKey ? resizeStep : 0, 0);
            break;
        case 'ArrowUp':
            e.preventDefault();
            compositor.adjustAnchor(0, e.shiftKey ? 0 : -step, 0, e.shiftKey ? -resizeStep : 0);
            break;
        case 'ArrowDown':
            e.preventDefault();
            compositor.adjustAnchor(0, e.shiftKey ? 0 : step, 0, e.shiftKey ? resizeStep : 0);
            break;
        case 'Tab':
            e.preventDefault();
            compositor.switchAnchor();
            break;
        case 'c':
        case 'C':
            calibrationToggle.checked = !calibrationToggle.checked;
            calibrationToggle.dispatchEvent(new Event('change'));
            break;
    }
    
    updateCalibrationInfo();
}

/**
 * Update calibration info display
 */
function updateCalibrationInfo() {
    if (!compositor.manifest) return;
    
    const mouthAnchor = compositor.getAdjustedAnchor('mouth');
    const eyesAnchor = compositor.getAdjustedAnchor('eyes');
    
    calibrationInfo.innerHTML = `
        <strong>Mouth:</strong> x:${mouthAnchor.x} y:${mouthAnchor.y} w:${mouthAnchor.w} h:${mouthAnchor.h}<br>
        <strong>Eyes:</strong> x:${eyesAnchor.x} y:${eyesAnchor.y} w:${eyesAnchor.w} h:${eyesAnchor.h}<br>
        <small>Use Arrow keys to adjust, Shift+Arrow to resize</small>
    `;
}

/**
 * Main render loop
 */
function renderLoop(timestamp) {
    if (animationState.isPlaying && audio) {
        const currentTimeMs = audio.currentTime * 1000;
        const deltaTime = (timestamp - animationState.lastFrameTime) / 1000;
        animationState.lastFrameTime = timestamp;
        
        // Update compositor
        compositor.update(
            currentTimeMs,
            animationState.mouthCues,
            animationState.eyeEvents,
            deltaTime
        );
        
        // Update playheads
        if (animationState.durationMs > 0) {
            const percent = (currentTimeMs / animationState.durationMs) * 100;
            mouthPlayhead.style.left = `${Math.min(percent, 100)}%`;
            eyePlayhead.style.left = `${Math.min(percent, 100)}%`;
        }
    }
    
    // Render
    compositor.render();
    
    requestAnimationFrame(renderLoop);
}

/**
 * Handle render button
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
 * Handle stop button
 */
function handleStop() {
    if (audio) {
        audio.pause();
        audio.currentTime = 0;
    }
    animationState.isPlaying = false;
    setStatus('ready', 'Stopped');
    compositor.reset();
}

/**
 * Play animation with audio
 */
async function playAnimation(data) {
    handleStop();

    // Set up animation state
    animationState.mouthCues = data.mouth_cues || [];
    animationState.eyeEvents = data.eye_events || [];
    animationState.durationMs = data.duration_ms || 0;

    // Create audio element
    audio = new Audio(data.audio_url);
    audio.crossOrigin = 'anonymous';

    return new Promise((resolve, reject) => {
        audio.oncanplaythrough = () => {
            audio.play().then(() => {
                animationState.isPlaying = true;
                animationState.startTime = performance.now();
                animationState.lastFrameTime = performance.now();
                setStatus('active', 'Playing...');
                resolve();
            }).catch(reject);
        };

        audio.onerror = () => {
            reject(new Error('Failed to load audio'));
        };

        audio.onended = () => {
            animationState.isPlaying = false;
            setStatus('ready', 'Playback complete');
            compositor.reset();
        };

        audio.load();
    });
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
 * Display API response
 */
function displayResponse(data) {
    const formatted = JSON.stringify(data, null, 2);
    const highlighted = formatted
        .replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:')
        .replace(/: "([^"]*)"([,\n])/g, ': <span class="json-string">"$1"</span>$2')
        .replace(/: (-?\d+\.?\d*)([,\n])/g, ': <span class="json-number">$1</span>$2')
        .replace(/: (true|false)([,\n])/g, ': <span class="json-boolean">$1</span>$2');
    
    responseJson.innerHTML = highlighted;

    const cached = data.cached ? ' (cached)' : '';
    const duration = data.duration_ms ? `${(data.duration_ms / 1000).toFixed(2)}s` : 'N/A';
    const processingTime = data.processing_time_ms ? `${data.processing_time_ms}ms` : 'N/A';
    responseMeta.textContent = `Duration: ${duration} | Processing: ${processingTime}${cached}`;

    if (data.mouth_cues && data.eye_events && data.duration_ms) {
        displayTimeline(data.mouth_cues, data.eye_events, data.duration_ms);
    }
}

/**
 * Display error
 */
function displayError(message) {
    responseJson.innerHTML = `<span style="color: var(--error)">Error: ${message}</span>`;
    responseMeta.textContent = '';
}

/**
 * Display timeline
 */
function displayTimeline(mouthCues, eyeEvents, durationMs) {
    timelinePanel.style.display = 'block';

    mouthTimeline.querySelectorAll('.timeline-marker').forEach(el => el.remove());
    eyeTimeline.querySelectorAll('.timeline-marker').forEach(el => el.remove());

    const visemeColors = {
        REST: '#6b7280',
        AA: '#ef4444',
        EE: '#f59e0b',
        OH: '#22c55e',
        OO: '#3b82f6',
        FF: '#8b5cf6',
        TH: '#ec4899',
    };

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

    const eyeEventColors = {
        blink: '#fbbf24',
        saccade: '#60a5fa',
    };

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
 * Idle animation (when not playing)
 */
function startIdleAnimation() {
    let lastBlink = 0;
    let blinking = false;
    let blinkProgress = 0;

    function idleLoop(timestamp) {
        if (animationState.isPlaying) {
            // Playing animation, skip idle
            requestAnimationFrame(idleLoop);
            return;
        }

        // Random blinking
        if (!blinking && timestamp - lastBlink > 3000 + Math.random() * 4000) {
            blinking = true;
            blinkProgress = 0;
            lastBlink = timestamp;
        }

        if (blinking) {
            blinkProgress += 0.1;
            if (blinkProgress >= 1.0) {
                blinking = false;
            } else {
                // Simulate blink in compositor
                const blinkEvent = [{
                    t_ms: 0,
                    event_type: 'blink',
                    duration_ms: 150
                }];
                compositor.updateEyeState(blinkProgress * 150, blinkEvent);
            }
        }

        requestAnimationFrame(idleLoop);
    }

    idleLoop(performance.now());
}

// Initialize on load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
