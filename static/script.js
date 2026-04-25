/* ── DOM refs ──────────────────────────────────────── */
const videoInput      = document.getElementById('videoInput');
const dropzone        = document.getElementById('dropzone');
const fileInfo        = document.getElementById('fileInfo');
const fileName        = document.getElementById('fileName');
const fileSize        = document.getElementById('fileSize');
const clearBtn        = document.getElementById('clearBtn');
const runBtn          = document.getElementById('runBtn');
const progressSection = document.getElementById('progressSection');
const resultsSection  = document.getElementById('resultsSection');
const procLog         = document.getElementById('procLog');

/* ── Drag & drop ───────────────────────────────────── */
dropzone.addEventListener('dragover', e => {
  e.preventDefault();
  dropzone.classList.add('drag-over');
});
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
dropzone.addEventListener('drop', e => {
  e.preventDefault();
  dropzone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f && f.type.startsWith('video/')) setFile(f);
});

videoInput.addEventListener('change', () => {
  if (videoInput.files.length) setFile(videoInput.files[0]);
});

clearBtn.addEventListener('click', () => {
  videoInput.value = '';
  fileInfo.style.display = 'none';
  runBtn.disabled = true;
});

function setFile(f) {
  fileName.textContent = f.name;
  fileSize.textContent = formatBytes(f.size);
  fileInfo.style.display = 'flex';
  runBtn.disabled = false;
  // also set the actual input so FormData picks it up
  const dt = new DataTransfer();
  dt.items.add(f);
  videoInput.files = dt.files;
}

function formatBytes(n) {
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB';
  return (n / (1024 * 1024)).toFixed(1) + ' MB';
}

/* ── Lane state machine ────────────────────────────── */
const lanes = {
  youtube:   { fill: 'fillYt',  msg: 'msgYt'  },
  instagram: { fill: 'fillIg',  msg: 'msgIg'  },
  x:         { fill: 'fillX',   msg: 'msgX'   },
};

function setLane(agent, status, msg) {
  const lane = lanes[agent];
  if (!lane) return;
  const fill  = document.getElementById(lane.fill);
  const msgEl = document.getElementById(lane.msg);
  if (fill)  fill.className = 'pl-fill ' + status;
  if (msgEl) msgEl.textContent = msg || '';
}

function resetLanes() {
  Object.keys(lanes).forEach(a => setLane(a, '', 'Queued'));
}

/* ── Process button ────────────────────────────────── */
runBtn.addEventListener('click', async () => {
  const files = videoInput.files;
  if (!files || files.length === 0) {
    showError('Please select a video file first.');
    return;
  }

  // UI: switch to processing mode
  runBtn.disabled = true;
  runBtn.querySelector('span').textContent = 'Processing…';
  progressSection.style.display = 'block';
  resultsSection.style.display  = 'none';
  procLog.textContent = 'Uploading video to server…';
  progressSection.scrollIntoView({ behavior: 'smooth' });
  resetLanes();

  // Build form data
  const formData = new FormData();
  formData.append('video', files[0]);

  // POST to /upload — server responds with SSE stream
  let response;
  try {
    response = await fetch('/upload', {
      method: 'POST',
      body:   formData,
    });
  } catch (err) {
    showError('Network error: ' + err.message);
    resetBtn();
    return;
  }

  if (!response.ok) {
    showError('Server returned ' + response.status);
    resetBtn();
    return;
  }

  // Read the SSE stream line by line
  const reader  = response.body.getReader();
  const decoder = new TextDecoder();
  let   buffer  = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by double newlines
    const frames = buffer.split('\n\n');
    buffer = frames.pop(); // keep the last incomplete frame

    for (const frame of frames) {
      const line = frame.trim();
      if (!line.startsWith('data:')) continue;
      let event;
      try {
        event = JSON.parse(line.slice(5).trim());
      } catch {
        continue;
      }
      handleEvent(event);
    }
  }
});

/* ── Handle one SSE event ──────────────────────────── */
function handleEvent(ev) {
  const { agent, status, msg, results, error } = ev;

  if (agent === 'ping') return;

  if (agent === 'complete') {
    procLog.textContent = '✅ All agents finished!';
    // Mark any still-running lanes as done
    Object.keys(lanes).forEach(a => {
      const fill = document.getElementById(lanes[a].fill);
      if (fill && !fill.classList.contains('done') && !fill.classList.contains('error')) {
        setLane(a, 'done', '✅ Done');
      }
    });
    displayResults(results || {});
    resetBtn();
    return;
  }

  // Per-agent progress event
  procLog.textContent = msg || '';
  if (lanes[agent]) {
    const cssStatus = status === 'done' ? 'done'
                    : status === 'error' ? 'error'
                    : 'running';
    setLane(agent, cssStatus, msg || '');
  }

  if (status === 'error' && error) {
    showError(`${agent} error:\n${error}`);
  }
}

/* ── Display results ───────────────────────────────── */
function displayResults(results) {
  resultsSection.style.display = 'block';
  resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

  /* ── YouTube: three videos ────────────────────────── */
  const yt = results.youtube;
  if (yt) {
    if (yt.shorts_exists && yt.shorts_url) {
      loadVideo('ytShorts', yt.shorts_url);
      setDownload('dlShorts', yt.shorts_url, 'youtube_short.mp4');
      document.getElementById('colYt').style.display = '';
    }
    if (yt.subtitled_exists && yt.subtitled_url) {
      loadVideo('ytFull', yt.subtitled_url);
      setDownload('dlSubtitled', yt.subtitled_url, 'youtube_subtitled.mp4');
    }
    if (yt.hindi_dubbed_exists && yt.hindi_dubbed_url) {
      loadVideo('ytHindi', yt.hindi_dubbed_url);
      setDownload('dlHindi', yt.hindi_dubbed_url, 'youtube_hindi_dubbed.mp4');
    }
    if (yt.community_post) {
      document.getElementById('communityText').textContent = yt.community_post;
      document.getElementById('communityCard').style.display = '';
    }
  }

  /* ── Instagram ────────────────────────────────────── */
  const ig = results.instagram;
  if (ig && ig.reel_exists && ig.reel_url) {
    loadVideo('igReel', ig.reel_url);
    setDownload('dlReel', ig.reel_url, 'instagram_reel.mp4');
    document.getElementById('colIg').style.display = '';
  }

  /* ── X ───────────────────────────────────────────── */
  const xd = results.x;
  if (xd) {
    if (xd.video_exists && xd.video_url) {
      loadVideo('xClip', xd.video_url);
      setDownload('dlX', xd.video_url, 'x_clip.mp4');
    }
    if (xd.description) {
      document.getElementById('xDesc').textContent = xd.description;
    }
    if (xd.category) {
      document.getElementById('xCategory').textContent = '📌 ' + xd.category;
    }
    document.getElementById('colX').style.display = '';
  }
}

function loadVideo(id, src) {
  const el = document.getElementById(id);
  if (!el) return;
  el.src = src;
  el.load();
}

function setDownload(id, href, filename) {
  const el = document.getElementById(id);
  if (!el) return;
  el.href     = href;
  el.download = filename;
}

/* ── Copy text to clipboard ────────────────────────── */
function copyText(id, btn) {
  const el = document.getElementById(id);
  if (!el) return;
  navigator.clipboard.writeText(el.textContent).then(() => {
    const orig = btn.textContent;
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.textContent = orig;
      btn.classList.remove('copied');
    }, 2000);
  }).catch(() => {
    // Fallback for older browsers
    const range = document.createRange();
    range.selectNode(el);
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
    document.execCommand('copy');
  });
}

/* ── Error toast ───────────────────────────────────── */
function showError(msg) {
  const toast = document.getElementById('errToast');
  document.getElementById('errMsg').textContent = msg;
  toast.style.display = 'flex';
  setTimeout(() => { toast.style.display = 'none'; }, 12000);
}

/* ── Reset run button ──────────────────────────────── */
function resetBtn() {
  runBtn.disabled = false;
  runBtn.querySelector('span').textContent = 'Process All Platforms';
}