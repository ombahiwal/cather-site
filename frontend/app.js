// frontend/app.js
const dom = {
  screens: {
    upload: document.getElementById('screenUpload'),
    results: document.getElementById('screenResults'),
  },
  inputs: {
    gallery: document.getElementById('imageInput'),
    camera: document.getElementById('cameraInput'),
  },
  buttons: {
    analyze: document.getElementById('analyzeBtn'),
    camera: document.getElementById('cameraBtn'),
    newScan: document.getElementById('newScanBtn'),
  },
  status: document.getElementById('status'),
  summary: {
    label: document.getElementById('label'),
    risk: document.getElementById('risk'),
    explanation: document.getElementById('explanation'),
    confidence: document.getElementById('confidence'),
    dot: document.getElementById('statusDot'),
  },
  indicatorList: document.getElementById('indicatorList'),
  jsonView: document.getElementById('rawjson'),
  historyList: document.getElementById('historyList'),
  cameraOverlay: document.getElementById('cameraOverlay'),
  cameraStream: document.getElementById('cameraStream'),
  captureBtn: document.getElementById('captureBtn'),
  closeCameraBtn: document.getElementById('closeCameraBtn'),
};

let mediaStream;
let cachedHistory = [];

const featureLabels = {
  redness: 'Redness',
  swelling: 'Swelling',
  dressing_lift: 'Dressing lift',
  discharge: 'Discharge',
  exposed_catheter: 'Exposed catheter',
  open_wound: 'Open wound',
  bruising: 'Bruising',
  crusting: 'Crusting',
  erythema_border_sharp: 'Sharp erythema border',
  fluctuance: 'Fluctuance',
};

const confidenceClass = (value) => {
  if (value >= 0.75) return 'chip success';
  if (value >= 0.45) return 'chip warn';
  if (value > 0) return 'chip muted';
  return 'chip muted';
};

const setScreen = (name) => {
  Object.entries(dom.screens).forEach(([key, el]) => {
    const active = key === name;
    el.classList.toggle('active', active);
    el.setAttribute('aria-hidden', (!active).toString());
  });
};

const setStatus = (message, type = '') => {
  dom.status.textContent = message;
  dom.status.className = ['status', type].filter(Boolean).join(' ');
};

const toggleLoading = (isLoading) => {
  dom.buttons.analyze.disabled = isLoading;
  dom.buttons.camera.disabled = isLoading;
  dom.buttons.analyze.textContent = isLoading ? 'Analyzing…' : 'Analyze photo';
};

const renderSummary = (classification) => {
  dom.summary.label.textContent = classification.label;
  dom.summary.risk.textContent = `Risk score: ${classification.risk_score}`;
  dom.summary.explanation.textContent = classification.explanation;
  dom.summary.confidence.textContent = `Confidence ${(classification.overall_confidence * 100).toFixed(0)}%`;
  dom.summary.confidence.className = confidenceClass(classification.overall_confidence || 0);
  setStatusDot(classification.label);
};

const setStatusDot = (label = '') => {
  const normalized = label.toLowerCase();
  const color = {
    red: 'red',
    yellow: 'yellow',
    green: 'green',
    uncertain: 'uncertain',
  }[normalized] || 'neutral';
  dom.summary.dot.className = `status-dot ${color}`;
  dom.summary.dot.title = `${label} indicator`;
};

const describeFeature = (name, value) => {
  if (!value) return 'Not detected';
  if (name === 'discharge' && value.present) {
    return `${value.type || 'discharge'} present${value.amount ? ` (${value.amount})` : ''}`;
  }
  if (name === 'redness' && value.present) {
    return `Extent ${value.extent_percent ?? 0}%`;
  }
  if (name === 'swelling' && value.present) {
    return `Extent ${value.extent_percent ?? 0}%`;
  }
  if (name === 'erythema_border_sharp') {
    return value.yes ? 'Defined border' : 'Diffuse border';
  }
  return value.present ? 'Present' : 'Not detected';
};

const indicatorClass = (name, value) => {
  if (!value) return 'indicator neutral';
  if (name === 'dressing_lift' && value.present) return 'indicator alert';
  if (name === 'discharge' && value.present) return 'indicator danger';
  if (name === 'open_wound' && value.present) return 'indicator danger';
  if (value.present || value.yes) return 'indicator alert';
  return 'indicator neutral';
};

const renderIndicators = (features = {}) => {
  const entries = Object.entries(featureLabels);
  if (!entries.length) {
    dom.indicatorList.innerHTML = '<p class="note">No indicators returned.</p>';
    return;
  }
  dom.indicatorList.innerHTML = entries.map(([key, label]) => {
    const value = features[key];
    const present = value?.present || value?.yes || false;
    return `
      <div class="${indicatorClass(key, value)}">
        <strong>${label}</strong>
        <span>${describeFeature(key, value)}</span>
        <span>${present ? '⚠︎' : '✔︎'}</span>
      </div>
    `;
  }).join('');
};

const renderDocument = (payload) => {
  dom.jsonView.textContent = JSON.stringify(payload, null, 2);
};

const formatTimestamp = (iso) => {
  if (!iso) return 'Unknown time';
  try {
    return new Date(iso).toLocaleString();
  } catch (err) {
    return iso;
  }
};

const renderHistory = (entries = []) => {
  cachedHistory = entries;
  if (!entries.length) {
    dom.historyList.innerHTML = '<p class="note">No assessments stored yet.</p>';
    return;
  }
  dom.historyList.innerHTML = entries.map((entry) => {
    const label = entry.classification?.label || 'Unknown';
    return `
      <div class="history-item">
        <img src="${entry.image_url}" alt="Assessment image" loading="lazy" />
        <div class="history-meta">
          <strong>${label}</strong>
          <span>${formatTimestamp(entry.timestamp)}</span>
        </div>
        <button type="button" data-history-id="${entry.id}">View</button>
      </div>
    `;
  }).join('');
};

const fetchHistory = async () => {
  try {
    const res = await fetch('/history');
    if (!res.ok) throw new Error('Unable to load history');
    const data = await res.json();
    renderHistory(data);
  } catch (error) {
    console.warn(error);
  }
};

const displayHistoryEntry = (id) => {
  const entry = cachedHistory.find((item) => item.id === id);
  if (!entry) return;
  renderSummary(entry.classification);
  renderIndicators(entry.gemini?.features);
  renderDocument(entry);
  setScreen('results');
  setStatus('Displaying saved assessment', 'success');
};

const closeCamera = () => {
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }
  dom.cameraOverlay.classList.remove('open');
  dom.cameraOverlay.setAttribute('aria-hidden', 'true');
};

const openCamera = async () => {
  if (!navigator.mediaDevices?.getUserMedia) {
    dom.inputs.camera.click();
    return;
  }
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } } });
    dom.cameraStream.srcObject = mediaStream;
    dom.cameraOverlay.classList.add('open');
    dom.cameraOverlay.setAttribute('aria-hidden', 'false');
  } catch (error) {
    console.error(error);
    setStatus('Camera access blocked. Please allow camera or upload from gallery.', 'error');
    dom.inputs.camera.click();
  }
};

const captureFrame = () => {
  const video = dom.cameraStream;
  if (!mediaStream || !video.videoWidth) {
    setStatus('Unable to access camera stream', 'error');
    return;
  }
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  canvas.toBlob((blob) => {
    if (!blob) {
      setStatus('Capture failed. Try again.', 'error');
      return;
    }
    const file = new File([blob], `camera-${Date.now()}.jpg`, { type: 'image/jpeg' });
    closeCamera();
    runAnalysis(file);
  }, 'image/jpeg', 0.9);
};

const runAnalysis = async (file) => {
  const form = new FormData();
  form.append('image', file, file.name || 'capture.jpg');

  setStatus('Analyzing image…', 'loading');
  toggleLoading(true);

  try {
    const res = await fetch('/analyze', { method: 'POST', body: form });
    if (!res.ok) {
      const payload = await res.json().catch(async () => ({ error: await res.text() }));
      throw new Error(payload.error || 'Unexpected server error');
    }
    const data = await res.json();
    renderSummary(data.classification);
    renderIndicators(data.gemini?.features);
    renderDocument(data);
    setScreen('results');
    setStatus('Analysis complete', 'success');
    fetchHistory();
  } catch (error) {
    console.error(error);
    setStatus(error.message || 'Failed to analyze image', 'error');
  } finally {
    toggleLoading(false);
  }
};

dom.buttons.analyze.addEventListener('click', () => {
  const files = dom.inputs.gallery.files;
  if (!files || files.length === 0) {
    setStatus('Please choose an image first', 'error');
    return;
  }
  runAnalysis(files[0]);
});

dom.buttons.camera.addEventListener('click', openCamera);

dom.inputs.camera.addEventListener('change', () => {
  const files = dom.inputs.camera.files;
  if (files && files[0]) {
    runAnalysis(files[0]);
  }
});

dom.buttons.newScan.addEventListener('click', () => {
  dom.inputs.gallery.value = '';
  dom.inputs.camera.value = '';
  setScreen('upload');
  setStatus('Ready for another capture');
});

dom.historyList.addEventListener('click', (event) => {
  if (event.target.matches('[data-history-id]')) {
    displayHistoryEntry(event.target.getAttribute('data-history-id'));
  }
});

dom.captureBtn.addEventListener('click', captureFrame);
dom.closeCameraBtn.addEventListener('click', closeCamera);

window.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    closeCamera();
  }
});

window.addEventListener('load', () => {
  fetchHistory();
});
