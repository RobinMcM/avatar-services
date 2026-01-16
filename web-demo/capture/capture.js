/**
 * Capture Studio - Avatar Recording and Processing
 */

// Capture Timeline (fixed timestamps in seconds)
const CAPTURE_TIMELINE = [
    { start: 0, end: 5, segment: 'idle', prompt: 'Stay still and breathe naturally', beep: false },
    { start: 5, end: 7, segment: 'rest', prompt: 'REST - Close your mouth', beep: true },
    { start: 7, end: 9, segment: 'aa', prompt: 'AA - Say "AH"', beep: true },
    { start: 9, end: 11, segment: 'ee', prompt: 'EE - Say "EEE"', beep: true },
    { start: 11, end: 13, segment: 'oh', prompt: 'OH - Say "OH"', beep: true },
    { start: 13, end: 15, segment: 'oo', prompt: 'OO - Say "OOO"', beep: true },
    { start: 15, end: 17, segment: 'ff', prompt: 'FF - Say "FFF"', beep: true },
    { start: 17, end: 19, segment: 'th', prompt: 'TH - Stick tongue out', beep: true },
    { start: 19, end: 25, segment: 'blinks', prompt: 'Blink naturally 5 times', beep: true },
    { start: 25, end: 27, segment: 'eyes_open', prompt: 'Eyes OPEN wide', beep: true },
    { start: 27, end: 29, segment: 'eyes_half', prompt: 'Eyes HALF closed (squint)', beep: true },
    { start: 29, end: 31, segment: 'eyes_closed', prompt: 'Eyes fully CLOSED', beep: true },
    { start: 31, end: 33, segment: 'gaze_left', prompt: 'Look LEFT', beep: true },
    { start: 33, end: 35, segment: 'gaze_right', prompt: 'Look RIGHT', beep: true },
    { start: 35, end: 37, segment: 'gaze_up', prompt: 'Look UP', beep: true },
    { start: 37, end: 39, segment: 'gaze_down', prompt: 'Look DOWN', beep: true },
    { start: 39, end: 42, segment: 'finish', prompt: 'Done! Stay still...', beep: false }
];

const TOTAL_DURATION = 42; // seconds
const API_BASE_URL = window.location.origin;

// State
let currentStep = 'setup';
let mediaStream = null;
let mediaRecorder = null;
let recordedChunks = [];
let recordingStartTime = 0;
let recordingInterval = null;
let avatarId = '';
let jobId = null;

// Audio Context for beeps
let audioContext = null;

// Initialize
document.addEventListener('DOMContentLoaded', init);

async function init() {
    setupEventListeners();
    await detectCameras();
}

function setupEventListeners() {
    document.getElementById('start-setup-btn').addEventListener('click', startSetup);
    document.getElementById('back-to-setup-btn').addEventListener('click', () => showStep('setup'));
    document.getElementById('start-recording-btn').addEventListener('click', startRecording);
    document.getElementById('stop-recording-btn').addEventListener('click', stopRecording);
    document.getElementById('create-another-btn').addEventListener('click', () => location.reload());
    document.getElementById('dismiss-error-btn').addEventListener('click', dismissError);
    
    // Avatar ID input validation
    const avatarInput = document.getElementById('avatar-id-input');
    avatarInput.addEventListener('input', (e) => {
        e.target.value = e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '');
        validateSetup();
    });
    
    // Camera select change
    document.getElementById('camera-select').addEventListener('change', validateSetup);
}

async function detectCameras() {
    try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoDevices = devices.filter(d => d.kind === 'videoinput');
        
        const select = document.getElementById('camera-select');
        select.innerHTML = '';
        
        if (videoDevices.length === 0) {
            select.innerHTML = '<option>No cameras found</option>';
            showError('No cameras detected. Please connect a camera and reload the page.');
            return;
        }
        
        videoDevices.forEach((device, index) => {
            const option = document.createElement('option');
            option.value = device.deviceId;
            option.textContent = device.label || `Camera ${index + 1}`;
            select.appendChild(option);
        });
        
        validateSetup();
    } catch (error) {
        console.error('Error detecting cameras:', error);
        showError('Failed to detect cameras. Please allow camera access and reload.');
    }
}

function validateSetup() {
    const avatarInput = document.getElementById('avatar-id-input');
    const cameraSelect = document.getElementById('camera-select');
    const startBtn = document.getElementById('start-setup-btn');
    
    const isValid = avatarInput.value.length >= 3 && cameraSelect.value !== '';
    startBtn.disabled = !isValid;
}

async function startSetup() {
    avatarId = document.getElementById('avatar-id-input').value;
    const deviceId = document.getElementById('camera-select').value;
    
    try {
        // Request camera access
        const constraints = {
            video: {
                deviceId: deviceId ? { exact: deviceId } : undefined,
                width: { ideal: 1280 },
                height: { ideal: 1600 },
                facingMode: 'user'
            },
            audio: true
        };
        
        mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
        
        // Show preview in alignment step
        showStep('alignment');
        const previewVideo = document.getElementById('preview-video');
        const recordingVideo = document.getElementById('recording-video');
        previewVideo.srcObject = mediaStream;
        recordingVideo.srcObject = mediaStream;
        
    } catch (error) {
        console.error('Error accessing camera:', error);
        showError('Failed to access camera. Please allow camera and microphone access.');
    }
}

function startRecording() {
    showStep('recording');
    
    // Initialize audio context for beeps
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    
    // Setup MediaRecorder
    const options = {
        mimeType: 'video/webm;codecs=vp9,opus',
        videoBitsPerSecond: 2500000
    };
    
    // Fallback if VP9 not supported
    if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        options.mimeType = 'video/webm;codecs=vp8,opus';
    }
    
    recordedChunks = [];
    mediaRecorder = new MediaRecorder(mediaStream, options);
    
    mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
            recordedChunks.push(event.data);
        }
    };
    
    mediaRecorder.onstop = handleRecordingComplete;
    
    // Start recording with countdown
    let countdown = 3;
    const promptText = document.getElementById('prompt-text');
    const promptCountdown = document.getElementById('prompt-countdown');
    
    promptText.textContent = 'Get ready...';
    promptCountdown.textContent = countdown;
    
    const countdownInterval = setInterval(() => {
        countdown--;
        if (countdown > 0) {
            promptCountdown.textContent = countdown;
            playBeep(800, 0.1);
        } else {
            clearInterval(countdownInterval);
            promptCountdown.textContent = '';
            playBeep(1000, 0.2);
            actuallyStartRecording();
        }
    }, 1000);
}

function actuallyStartRecording() {
    mediaRecorder.start(100); // Collect data every 100ms
    recordingStartTime = Date.now();
    
    // Start timeline
    runRecordingTimeline();
    
    // Update progress
    recordingInterval = setInterval(updateRecordingProgress, 100);
}

function runRecordingTimeline() {
    let currentSegmentIndex = 0;
    
    function updatePrompt() {
        const elapsed = (Date.now() - recordingStartTime) / 1000;
        
        // Find current segment
        const segment = CAPTURE_TIMELINE.find(s => elapsed >= s.start && elapsed < s.end);
        
        if (!segment) {
            // Recording complete
            stopRecording();
            return;
        }
        
        // Check if we just entered a new segment
        if (CAPTURE_TIMELINE.indexOf(segment) !== currentSegmentIndex) {
            currentSegmentIndex = CAPTURE_TIMELINE.indexOf(segment);
            
            // Update display
            document.getElementById('prompt-text').textContent = segment.prompt;
            document.getElementById('current-segment').textContent = segment.segment.toUpperCase();
            
            // Play beep if needed
            if (segment.beep) {
                playBeep(1200, 0.15);
            }
        }
        
        // Update countdown for current segment
        const segmentRemaining = segment.end - elapsed;
        document.getElementById('prompt-countdown').textContent = `${Math.ceil(segmentRemaining)}s`;
        
        // Continue
        requestAnimationFrame(updatePrompt);
    }
    
    updatePrompt();
}

function updateRecordingProgress() {
    const elapsed = (Date.now() - recordingStartTime) / 1000;
    const progress = (elapsed / TOTAL_DURATION) * 100;
    
    document.getElementById('recording-progress').style.width = `${Math.min(progress, 100)}%`;
    document.getElementById('recording-time').textContent = `${Math.floor(elapsed)}s`;
    
    // Auto-stop at end
    if (elapsed >= TOTAL_DURATION) {
        stopRecording();
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    }
    
    if (recordingInterval) {
        clearInterval(recordingInterval);
        recordingInterval = null;
    }
    
    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        mediaStream = null;
    }
}

function handleRecordingComplete() {
    // Create blob from recorded chunks
    const blob = new Blob(recordedChunks, { type: 'video/webm' });
    
    console.log(`Recording complete: ${blob.size} bytes`);
    
    // Validate size
    if (blob.size < 100000) {
        showError('Recording too small. Please try again.');
        showStep('setup');
        return;
    }
    
    // Proceed to upload
    showStep('processing');
    uploadRecording(blob);
}

async function uploadRecording(blob) {
    updateStatus('⏳', 'Uploading recording...', '0%');
    
    try {
        const formData = new FormData();
        formData.append('video', blob, `${avatarId}.webm`);
        formData.append('avatar_id', avatarId);
        
        const xhr = new XMLHttpRequest();
        
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percent = Math.round((e.loaded / e.total) * 100);
                updateStatus('⏳', 'Uploading recording...', `${percent}%`);
            }
        });
        
        xhr.addEventListener('load', async () => {
            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                console.log('Upload complete:', response);
                addLog('✓ Upload complete');
                
                // Start processing
                await startProcessing(response.capture_id);
            } else {
                const error = JSON.parse(xhr.responseText);
                showError(`Upload failed: ${error.detail || 'Unknown error'}`);
            }
        });
        
        xhr.addEventListener('error', () => {
            showError('Upload failed due to network error. Please try again.');
        });
        
        xhr.open('POST', `${API_BASE_URL}/v1/capture/upload`);
        xhr.send(formData);
        
    } catch (error) {
        console.error('Upload error:', error);
        showError(`Upload failed: ${error.message}`);
    }
}

async function startProcessing(captureId) {
    updateStatus('⚙️', 'Starting processing...', '');
    addLog('→ Starting avatar pack generation...');
    
    try {
        const response = await fetch(`${API_BASE_URL}/v1/capture/process`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                capture_id: captureId,
                avatar_id: avatarId
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Processing failed to start');
        }
        
        const data = await response.json();
        jobId = data.job_id;
        
        addLog(`✓ Job started: ${jobId}`);
        
        // Poll for status
        pollJobStatus();
        
    } catch (error) {
        console.error('Processing error:', error);
        showError(`Processing failed: ${error.message}`);
    }
}

async function pollJobStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/v1/capture/jobs/${jobId}`);
        
        if (!response.ok) {
            throw new Error('Failed to fetch job status');
        }
        
        const data = await response.json();
        
        // Update UI
        if (data.progress !== undefined) {
            updateStatus('⚙️', data.status || 'Processing...', `${data.progress}%`);
        }
        
        // Add logs
        if (data.logs && Array.isArray(data.logs)) {
            data.logs.forEach(log => addLog(log));
        }
        
        // Check status
        if (data.status === 'completed') {
            handleProcessingComplete(data);
        } else if (data.status === 'failed') {
            showError(data.error || 'Processing failed');
        } else {
            // Continue polling
            setTimeout(pollJobStatus, 2000);
        }
        
    } catch (error) {
        console.error('Status poll error:', error);
        showError(`Failed to check status: ${error.message}`);
    }
}

function handleProcessingComplete(data) {
    updateStatus('✅', 'Complete!', '100%');
    addLog('✓ Avatar pack generated successfully!');
    
    // Show complete step
    showStep('complete');
    
    document.getElementById('final-avatar-id').textContent = avatarId;
    
    // Set up links
    const manifestUrl = data.manifest_url || `/avatars/${avatarId}/manifest.json`;
    const zipUrl = data.zip_url || `/avatars/${avatarId}.zip`;
    
    // Open in demo button - pass avatar ID as URL parameter
    document.getElementById('open-demo-btn').href = `/?avatar=${avatarId}`;
    
    // Download ZIP button
    document.getElementById('download-zip-btn').href = zipUrl;
}

function playBeep(frequency, duration) {
    if (!audioContext) return;
    
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    oscillator.frequency.value = frequency;
    oscillator.type = 'sine';
    
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + duration);
    
    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + duration);
}

function showStep(step) {
    // Hide all steps
    document.querySelectorAll('.step').forEach(el => el.classList.remove('active'));
    
    // Show target step
    document.getElementById(`step-${step}`).classList.add('active');
    
    currentStep = step;
}

function updateStatus(icon, text, progress) {
    document.getElementById('status-icon').textContent = icon;
    document.getElementById('status-text').textContent = text;
    document.getElementById('status-progress').textContent = progress;
}

function addLog(message) {
    const logDiv = document.getElementById('processing-log');
    const entry = document.createElement('div');
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    logDiv.appendChild(entry);
    logDiv.scrollTop = logDiv.scrollHeight;
}

function showError(message) {
    const errorDisplay = document.getElementById('error-display');
    const errorMessage = document.getElementById('error-message');
    
    errorMessage.textContent = message;
    errorDisplay.style.display = 'block';
    
    console.error('Error:', message);
}

function dismissError() {
    document.getElementById('error-display').style.display = 'none';
}
