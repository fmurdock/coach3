/* Coach3 Gym Mode Voice Logger — CSP-Compliant, Multi-Clause & Offline-Resilient */
(function () {
  'use strict';

  const { escapeHtml, safeUUID, showToast, authFetch } = window.Coach3;
  const KG_TO_LBS = 2.20462;
  const OFFLINE_QUEUE_KEY = 'coach3_gym_offline_queue_v1';

  let activeSessionId = null;
  let stagedData = null;
  let originalParsedSets = [];
  let loggedSets = [];

  const micBtn = document.getElementById('mic-btn');
  const micLabel = document.getElementById('mic-label');
  const manualInput = document.getElementById('manual-text');
  const manualParseBtn = document.getElementById('manual-parse-btn');
  const stagedSection = document.getElementById('staged-section');
  const stagedConfidence = document.getElementById('staged-confidence');
  const stagedTranscript = document.getElementById('staged-transcript');
  const stagedCardsContainer = document.getElementById('staged-cards-container');
  const btnCancel = document.getElementById('btn-cancel');
  const btnConfirm = document.getElementById('btn-confirm');
  const historyList = document.getElementById('history-list');
  const volumeTicker = document.getElementById('total-volume-ticker');
  const sessionBadge = document.getElementById('session-badge');
  const offlineBadge = document.getElementById('offline-queue-badge');

  // --- Offline Queue Helpers ---
  function readOfflineQueue() {
    try {
      const raw = localStorage.getItem(OFFLINE_QUEUE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
      return [];
    }
  }

  function writeOfflineQueue(queue) {
    try {
      localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(queue));
    } catch (_) {
      // Ignore storage quota errors
    }
    updateOfflineBadge();
  }

  function updateOfflineBadge() {
    const queue = readOfflineQueue();
    if (queue.length > 0) {
      offlineBadge.style.display = 'inline-flex';
      offlineBadge.textContent = `⏳ ${queue.length} pending offline sync — Tap to retry`;
    } else {
      offlineBadge.style.display = 'none';
    }
  }

  async function flushOfflineQueue() {
    const queue = readOfflineQueue();
    if (!queue.length || !navigator.onLine) return;

    const remaining = [];
    let syncedCount = 0;

    for (const item of queue) {
      const targetSessionId = item.sessionId || activeSessionId;
      if (!targetSessionId) {
        remaining.push(item);
        continue;
      }
      try {
        const res = await authFetch(`/api/v1/gym/sessions/${targetSessionId}/sets`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(item.payload),
        });
        if (res.ok) {
          syncedCount += 1;
        } else if (res.status >= 400 && res.status < 500) {
          // Validation error on queued item — drop to prevent infinite poison-pill retry
          const err = await res.json().catch(() => ({}));
          showToast(`Dropped invalid offline entry: ${err.detail || res.status}`, 'error');
        } else {
          remaining.push(item);
        }
      } catch (_) {
        remaining.push(item);
      }
    }

    writeOfflineQueue(remaining);
    if (syncedCount > 0) {
      showToast(`Synced ${syncedCount} offline set submission(s)!`, 'success');
      if (activeSessionId) {
        await loadSessionSets(activeSessionId);
      }
    }
  }

  offlineBadge.addEventListener('click', flushOfflineQueue);
  window.addEventListener('online', () => {
    showToast('Back online — syncing queued sets...', 'info');
    flushOfflineQueue();
  });

  // --- Session Initialization & Set Reload ---
  async function loadSessionSets(sessionId) {
    try {
      const res = await authFetch(`/api/v1/gym/sessions/${sessionId}/sets`);
      if (!res.ok) return;
      const sets = await res.json();
      loggedSets = Array.isArray(sets) ? sets.slice().reverse() : [];
      renderHistory();
    } catch (err) {
      console.error('Failed to load session sets:', err);
    }
  }

  async function initSession() {
    updateOfflineBadge();
    try {
      const res = await authFetch('/api/v1/gym/sessions/active');
      if (res.ok) {
        const session = await res.json();
        activeSessionId = session.id;
        sessionBadge.textContent = session.title || 'Strength Session';
        await loadSessionSets(activeSessionId);
        await flushOfflineQueue();
      }
    } catch (err) {
      console.error('Failed to init session:', err);
      sessionBadge.textContent = 'Offline Mode (Local Queue)';
    }
  }

  // --- Web Speech API ---
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let isListening = false;

  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      isListening = true;
      micBtn.classList.add('listening');
      micLabel.textContent = 'Listening... Speak your set';
    };

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      manualInput.value = transcript;
      parseTranscript(transcript);
    };

    recognition.onerror = (event) => {
      console.error('Speech error:', event.error);
      micLabel.textContent = 'Tap to try again';
      stopListening();
    };

    recognition.onend = () => stopListening();
  } else {
    micLabel.textContent = 'Voice dictation not supported in this browser. Use text input below.';
  }

  function stopListening() {
    isListening = false;
    micBtn.classList.remove('listening');
    micLabel.textContent = 'Tap microphone and speak your set';
  }

  micBtn.addEventListener('click', () => {
    if (!recognition) return;
    if (isListening) {
      recognition.stop();
      stopListening();
    } else {
      recognition.start();
    }
  });

  manualParseBtn.addEventListener('click', () => {
    const text = manualInput.value.trim();
    if (text) parseTranscript(text);
  });

  manualInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const text = e.target.value.trim();
      if (text) parseTranscript(text);
    }
  });

  // --- Parse Transcript ---
  async function parseTranscript(text) {
    try {
      micLabel.textContent = 'Parsing...';
      const res = await authFetch('/api/v1/gym/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript: text, default_unit: 'lbs' }),
      });

      if (!res.ok) throw new Error('Parsing failed');
      const data = await res.json();
      renderStagedCards(data);
      micLabel.textContent = 'Tap microphone and speak your set';
    } catch (err) {
      console.error(err);
      showToast('Could not parse workout statement. Try rephrasing.', 'error');
      micLabel.textContent = 'Tap microphone and speak your set';
    }
  }

  // --- Render ALL Multi-Clause Candidates ---
  function renderStagedCards(data) {
    stagedData = data;
    if (!data.parsed_sets || data.parsed_sets.length === 0) {
      const suggestionNames = (data.alternative_exercises || [])
        .map((a) => a.canonical_name)
        .join(', ');
      showToast(
        suggestionNames
          ? `Exercise ambiguous. Did you mean: ${suggestionNames}?`
          : 'Could not identify an exercise from statement. Please try again.',
        'error'
      );
      return;
    }

    originalParsedSets = JSON.parse(JSON.stringify(data.parsed_sets));
    stagedSection.style.display = 'block';
    stagedConfidence.textContent = `${Math.round((data.confidence_score || 0) * 100)}% match`;
    stagedTranscript.textContent = `"${data.raw_transcript}"`;

    stagedCardsContainer.innerHTML = '';

    data.parsed_sets.forEach((cand, idx) => {
      const block = document.createElement('div');
      block.className = 'candidate-block';
      block.dataset.index = String(idx);
      block.dataset.origExerciseId = cand.exercise_id || '';
      block.dataset.origExerciseName = cand.exercise_name || '';
      block.dataset.isBodyweight = cand.is_bodyweight ? 'true' : 'false';
      block.dataset.isWarmup = cand.is_warmup ? 'true' : 'false';
      block.dataset.category = cand.category || 'barbell';

      const weightLabelText = cand.is_bodyweight ? 'Added Load' : 'Weight';
      const weightVal = cand.is_bodyweight ? (cand.added_weight || 0) : (cand.weight || 0);

      block.innerHTML = `
        <div class="candidate-header">
          <span>Exercise ${idx + 1} of ${data.parsed_sets.length}</span>
          ${data.parsed_sets.length > 1 ? '<button type="button" class="btn-secondary btn-remove-cand" style="padding:2px 8px;font-size:11px;">Remove</button>' : ''}
        </div>
        <div class="edit-grid">
          <div class="field-group field-full">
            <label>Exercise</label>
            <input type="text" class="cand-exercise" value="${escapeHtml(cand.exercise_name)}" />
          </div>
          <div class="field-group">
            <label>Sets</label>
            <input type="number" class="cand-sets" min="1" value="${escapeHtml(cand.sets || 1)}" />
          </div>
          <div class="field-group">
            <label>Reps per set</label>
            <input type="number" class="cand-reps" min="1" value="${escapeHtml(cand.reps || 1)}" />
          </div>
          <div class="field-group">
            <label>${escapeHtml(weightLabelText)}</label>
            <input type="number" class="cand-weight" step="0.5" value="${escapeHtml(weightVal)}" />
          </div>
          <div class="field-group">
            <label>Unit</label>
            <select class="cand-unit">
              <option value="lbs" ${cand.weight_unit === 'lbs' ? 'selected' : ''}>lbs</option>
              <option value="kg" ${cand.weight_unit === 'kg' ? 'selected' : ''}>kg</option>
            </select>
          </div>
          <div class="field-group">
            <label>RPE (Optional)</label>
            <input type="number" class="cand-rpe" step="0.5" min="1" max="10" placeholder="e.g. 8.5" value="${cand.rpe != null ? escapeHtml(cand.rpe) : ''}" />
          </div>
          <div class="field-group">
            <label>Rest Seconds</label>
            <input type="number" class="cand-rest" step="15" placeholder="e.g. 120" value="${cand.rest_seconds != null ? escapeHtml(cand.rest_seconds) : ''}" />
          </div>
        </div>
      `;

      // Clear stale exercise_id whenever the user edits the exercise name!
      const exInput = block.querySelector('.cand-exercise');
      exInput.addEventListener('input', () => {
        if (exInput.value.trim().toLowerCase() !== (block.dataset.origExerciseName || '').trim().toLowerCase()) {
          block.dataset.exerciseIdCleared = 'true';
        } else {
          block.dataset.exerciseIdCleared = 'false';
        }
      });

      const removeBtn = block.querySelector('.btn-remove-cand');
      if (removeBtn) {
        removeBtn.addEventListener('click', () => {
          block.remove();
          if (!stagedCardsContainer.querySelector('.candidate-block')) {
            stagedSection.style.display = 'none';
            stagedData = null;
          }
        });
      }

      stagedCardsContainer.appendChild(block);
    });

    stagedSection.scrollIntoView({ behavior: 'smooth' });
  }

  btnCancel.addEventListener('click', () => {
    stagedSection.style.display = 'none';
    stagedData = null;
    originalParsedSets = [];
  });

  function collectEditedCandidates() {
    const blocks = Array.from(stagedCardsContainer.querySelectorAll('.candidate-block'));
    return blocks.map((block) => {
      const exerciseName = block.querySelector('.cand-exercise').value.trim();
      const setsCount = parseInt(block.querySelector('.cand-sets').value, 10) || 1;
      const repsCount = parseInt(block.querySelector('.cand-reps').value, 10) || 1;
      const weightVal = parseFloat(block.querySelector('.cand-weight').value) || 0;
      const unitVal = block.querySelector('.cand-unit').value || 'lbs';
      const rpeRaw = block.querySelector('.cand-rpe').value;
      const restRaw = block.querySelector('.cand-rest').value;
      const rpeVal = rpeRaw !== '' ? parseFloat(rpeRaw) : null;
      const restVal = restRaw !== '' ? parseInt(restRaw, 10) : null;
      const isBodyweight = block.dataset.isBodyweight === 'true';
      const isWarmup = block.dataset.isWarmup === 'true';
      const cleared = block.dataset.exerciseIdCleared === 'true';
      const exerciseId = cleared || !block.dataset.origExerciseId ? null : block.dataset.origExerciseId;

      return {
        exercise_id: exerciseId,
        exercise_name: exerciseName,
        category: block.dataset.category || 'barbell',
        sets: setsCount,
        reps: repsCount,
        weight: isBodyweight ? 0 : weightVal,
        weight_unit: unitVal,
        is_bodyweight: isBodyweight,
        added_weight: isBodyweight ? weightVal : 0,
        rpe: Number.isFinite(rpeVal) ? rpeVal : null,
        is_warmup: isWarmup,
        rest_seconds: Number.isFinite(restVal) ? restVal : null,
      };
    });
  }

  function computeWasEdited(edited, original) {
    if (edited.length !== original.length) return true;
    for (let i = 0; i < edited.length; i++) {
      const e = edited[i];
      const o = original[i];
      if (
        e.exercise_name !== o.exercise_name ||
        e.sets !== o.sets ||
        e.reps !== o.reps ||
        e.weight !== o.weight ||
        e.added_weight !== o.added_weight ||
        e.weight_unit !== o.weight_unit ||
        (e.rpe ?? null) !== (o.rpe ?? null) ||
        (e.rest_seconds ?? null) !== (o.rest_seconds ?? null)
      ) {
        return true;
      }
    }
    return false;
  }

  // --- Confirm & Commit Sets ---
  btnConfirm.addEventListener('click', async () => {
    if (!stagedData) return;

    const editedSets = collectEditedCandidates();
    if (!editedSets.length) return;

    const payload = {
      idempotency_key: safeUUID(),
      raw_transcript: stagedData.raw_transcript,
      confidence_score: stagedData.confidence_score,
      was_edited: computeWasEdited(editedSets, originalParsedSets),
      original_parsed_sets: originalParsedSets,
      sets: editedSets,
    };

    const queueOffline = () => {
      const queue = readOfflineQueue();
      queue.push({
        sessionId: activeSessionId,
        payload,
        queuedAt: new Date().toISOString(),
      });
      writeOfflineQueue(queue);
      showToast('Offline — queued set locally. Will auto-sync when connected.', 'info');
      stagedSection.style.display = 'none';
      manualInput.value = '';
      stagedData = null;
      originalParsedSets = [];
      renderHistory();
    };

    if (!navigator.onLine || !activeSessionId) {
      queueOffline();
      return;
    }

    btnConfirm.disabled = true;
    try {
      const res = await authFetch(`/api/v1/gym/sessions/${activeSessionId}/sets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Commit failed (HTTP ${res.status})`);
      }

      const committedSets = await res.json();
      committedSets.forEach((s) => loggedSets.unshift(s));
      renderHistory();

      stagedSection.style.display = 'none';
      manualInput.value = '';
      stagedData = null;
      originalParsedSets = [];
      showToast(`Logged ${committedSets.length} set(s)!`, 'success');
    } catch (err) {
      if (err instanceof TypeError) {
        // Network failure -> persist offline
        queueOffline();
      } else {
        showToast(err.message || 'Failed to save set.', 'error');
      }
    } finally {
      btnConfirm.disabled = false;
    }
  });

  // --- Delete / Undo Set Hook (wired to DELETE /api/v1/gym/sets/{id}) ---
  async function deleteSet(setId) {
    try {
      const res = await authFetch(`/api/v1/gym/sets/${setId}`, { method: 'DELETE' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Delete failed');
      }
      loggedSets = loggedSets.filter((s) => s.id !== setId);
      renderHistory();
      showToast('Set removed.', 'info');
    } catch (err) {
      showToast(err.message || 'Could not remove set.', 'error');
    }
  }

  // --- Render History Feed ---
  function renderHistory() {
    historyList.innerHTML = '';

    let totalVolumeLbs = 0;

    loggedSets.forEach((s) => {
      const unitFactor = s.weight_unit === 'kg' ? KG_TO_LBS : 1.0;
      const effectiveLoad = s.is_bodyweight ? Math.max(0, Number(s.added_weight || 0)) : Number(s.weight || 0);
      if (!s.is_warmup) {
        totalVolumeLbs += Number(s.reps_completed || 0) * effectiveLoad * unitFactor;
      }

      const item = document.createElement('div');
      item.className = 'set-item';

      const weightDisplay = s.is_bodyweight
        ? (s.added_weight > 0
            ? `BW +${s.added_weight} ${s.weight_unit}`
            : (s.added_weight < 0 ? `BW ${s.added_weight} ${s.weight_unit}` : 'Bodyweight'))
        : `${s.weight} ${s.weight_unit}`;

      const rpeDisplay = s.rpe ? ` • RPE ${s.rpe}` : '';
      const timeStr = new Date(s.completed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      item.innerHTML = `
        <div>
          <div class="set-meta-exercise">Set ${escapeHtml(s.set_index)}: ${escapeHtml(s.exercise_name)}</div>
          <div class="set-meta-sub">${escapeHtml(timeStr)}${escapeHtml(rpeDisplay)}</div>
        </div>
        <div class="set-stats">
          <div>
            <div class="set-stats-main">${escapeHtml(s.reps_completed)} reps @ ${escapeHtml(weightDisplay)}</div>
            <div class="set-stats-sub">${s.is_warmup ? 'Warmup Set' : 'Working Set'}</div>
          </div>
          <button type="button" class="btn-danger btn-delete-set" style="padding:4px 8px;font-size:12px;" title="Remove set">✕</button>
        </div>
      `;

      const delBtn = item.querySelector('.btn-delete-set');
      if (delBtn) {
        delBtn.addEventListener('click', () => deleteSet(s.id));
      }
      historyList.appendChild(item);
    });

    // Render any offline queued submissions visually as pending
    const pendingQueue = readOfflineQueue();
    pendingQueue.forEach((qItem) => {
      (qItem.payload.sets || []).forEach((ps) => {
        const div = document.createElement('div');
        div.className = 'set-item pending-sync';
        div.innerHTML = `
          <div>
            <div class="set-meta-exercise">⏳ Pending: ${escapeHtml(ps.exercise_name)}</div>
            <div class="set-meta-sub">Queued offline (${escapeHtml(ps.sets)} × ${escapeHtml(ps.reps)})</div>
          </div>
          <div class="set-stats">
            <div class="set-stats-main">${escapeHtml(ps.is_bodyweight ? `BW +${ps.added_weight}` : `${ps.weight} ${ps.weight_unit}`)}</div>
          </div>
        `;
        historyList.prepend(div);
      });
    });

    volumeTicker.textContent = `${Math.round(totalVolumeLbs).toLocaleString()} lbs volume`;
  }

  initSession();
})();
