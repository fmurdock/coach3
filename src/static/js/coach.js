/* Coach3 Adaptive AI Coach — CSP-Compliant, Safe Markdown, Res.ok Checked */
(function () {
  'use strict';

  const { escapeHtml, formatMarkdown, showToast, authFetch } = window.Coach3;

  let currentPhilosophies = [];
  let currentProviders = [];
  let selectedPhilosophyId = null;

  // --- Tabs ---
  document.querySelectorAll('.tab-btn[data-tab]').forEach((btn) => {
    btn.addEventListener('click', (event) => {
      const target = event.currentTarget;
      const tabId = target.getAttribute('data-tab');
      document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach((p) => p.classList.remove('active'));
      target.classList.add('active');
      const panel = document.getElementById('tab-' + tabId);
      if (panel) panel.classList.add('active');
    });
  });

  // --- Sliders ---
  document.getElementById('slider-zone2').addEventListener('input', (e) => {
    document.getElementById('val-zone2').textContent = e.target.value + '%';
  });
  document.getElementById('slider-ramp').addEventListener('input', (e) => {
    document.getElementById('val-ramp').textContent = e.target.value + '%';
  });
  document.getElementById('slider-rpe').addEventListener('input', (e) => {
    document.getElementById('val-rpe').textContent = e.target.value;
  });
  document.getElementById('slider-rest').addEventListener('input', (e) => {
    document.getElementById('val-rest').textContent = e.target.value;
  });

  // --- Providers ---
  async function loadProviders() {
    try {
      const res = await authFetch('/api/v1/coaching/providers');
      if (!res.ok) return;
      currentProviders = await res.json();

      const gemBadge = document.getElementById('gemini-status');
      const llamaBadge = document.getElementById('llama-status');
      gemBadge.textContent = 'Configured';
      gemBadge.className = 'badge';
      llamaBadge.textContent = 'Configured';
      llamaBadge.className = 'badge';

      currentProviders.forEach((p) => {
        if (p.provider_type === 'gemini') {
          document.getElementById('gemini-model').value = p.model_name;
          if (p.is_active) {
            gemBadge.textContent = 'Active Engine';
            gemBadge.className = 'badge badge-success';
          }
        } else if (p.provider_type === 'llama_cpp') {
          document.getElementById('llama-url').value = p.endpoint_url;
          document.getElementById('llama-model').value = p.model_name;
          if (p.is_active) {
            llamaBadge.textContent = 'Active Engine';
            llamaBadge.className = 'badge badge-success';
          }
        }
      });
    } catch (err) {
      console.error('Error loading providers:', err);
    }
  }

  async function testProvider(type) {
    const provider = currentProviders.find((p) => p.provider_type === type);
    const statusBadge = document.getElementById(type === 'gemini' ? 'gemini-status' : 'llama-status');
    statusBadge.textContent = 'Testing...';
    statusBadge.className = 'badge';

    if (!provider) {
      showToast('Please save the provider configuration first.', 'error');
      statusBadge.textContent = 'Unconfigured';
      return;
    }

    try {
      const res = await authFetch(`/api/v1/coaching/providers/${provider.id}/test`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'healthy') {
        statusBadge.textContent = `Healthy (${data.latency_ms}ms)`;
        statusBadge.className = 'badge badge-success';
        showToast('Provider verified healthy!', 'success');
      } else {
        statusBadge.textContent = data.status;
        statusBadge.className = 'badge badge-danger';
        showToast(`Health Check: ${data.message}`, 'error');
      }
    } catch (e) {
      statusBadge.textContent = 'Error';
      statusBadge.className = 'badge badge-danger';
      showToast(`Test failed: ${e.message}`, 'error');
    }
  }

  async function saveAndActivateProvider(type) {
    const payload = { provider_type: type };
    if (type === 'gemini') {
      payload.endpoint_url = 'https://generativelanguage.googleapis.com';
      payload.model_name = document.getElementById('gemini-model').value.trim();
      const key = document.getElementById('gemini-key').value.trim();
      if (key) payload.api_key = key;
    } else {
      payload.endpoint_url = document.getElementById('llama-url').value.trim();
      payload.model_name = document.getElementById('llama-model').value.trim();
    }

    try {
      const res = await authFetch('/api/v1/coaching/providers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Failed to save provider (HTTP ${res.status})`);
      }
      const saved = await res.json();

      const actRes = await authFetch(`/api/v1/coaching/providers/${saved.id}/activate`, { method: 'POST' });
      if (!actRes.ok) {
        const err = await actRes.json().catch(() => ({}));
        throw new Error(err.detail || 'Saved provider, but activation failed');
      }
      document.getElementById('gemini-key').value = '';
      showToast(`Activated ${type} successfully!`, 'success');
      await loadProviders();
    } catch (err) {
      showToast('Error saving provider: ' + err.message, 'error');
    }
  }

  document.getElementById('btn-test-gemini').addEventListener('click', () => testProvider('gemini'));
  document.getElementById('btn-save-gemini').addEventListener('click', () => saveAndActivateProvider('gemini'));
  document.getElementById('btn-test-llama').addEventListener('click', () => testProvider('llama_cpp'));
  document.getElementById('btn-save-llama').addEventListener('click', () => saveAndActivateProvider('llama_cpp'));

  // --- Philosophies ---
  async function loadPhilosophies() {
    try {
      const res = await authFetch('/api/v1/coaching/philosophies');
      if (!res.ok) return;
      currentPhilosophies = await res.json();

      const selector = document.getElementById('philosophy-selector');
      selector.innerHTML = '';
      currentPhilosophies.forEach((p) => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name + (p.is_active ? ' (Active)' : '');
        if (p.is_active) opt.selected = true;
        selector.appendChild(opt);
      });

      const active = currentPhilosophies.find((p) => p.is_active) || currentPhilosophies[0];
      if (active) populatePhilosophy(active);
    } catch (e) {
      console.error('Error loading philosophies:', e);
    }
  }

  function populatePhilosophy(p) {
    selectedPhilosophyId = p.id;
    document.getElementById('phil-name').value = p.name;
    document.getElementById('phil-description').value = p.description || '';
    document.getElementById('phil-modality').value = p.primary_modality || 'hybrid';
    document.getElementById('slider-zone2').value = p.target_zone2_pct;
    document.getElementById('val-zone2').textContent = p.target_zone2_pct + '%';
    document.getElementById('slider-ramp').value = p.max_weekly_volume_ramp_pct;
    document.getElementById('val-ramp').textContent = p.max_weekly_volume_ramp_pct + '%';
    document.getElementById('slider-rpe').value = p.max_rpe_threshold;
    document.getElementById('val-rpe').textContent = p.max_rpe_threshold;
    document.getElementById('slider-rest').value = p.min_rest_days_per_week;
    document.getElementById('val-rest').textContent = p.min_rest_days_per_week;
    document.getElementById('phil-notes').value = p.custom_context_notes || '';
  }

  document.getElementById('philosophy-selector').addEventListener('change', (e) => {
    const p = currentPhilosophies.find((x) => x.id === e.target.value);
    if (p) populatePhilosophy(p);
  });

  document.getElementById('btn-save-philosophy').addEventListener('click', async () => {
    const payload = {
      name: document.getElementById('phil-name').value.trim(),
      description: document.getElementById('phil-description').value.trim() || null,
      primary_modality: document.getElementById('phil-modality').value || 'hybrid',
      target_zone2_pct: parseFloat(document.getElementById('slider-zone2').value),
      max_weekly_volume_ramp_pct: parseFloat(document.getElementById('slider-ramp').value),
      max_rpe_threshold: parseFloat(document.getElementById('slider-rpe').value),
      min_rest_days_per_week: parseInt(document.getElementById('slider-rest').value, 10),
      custom_context_notes: document.getElementById('phil-notes').value,
    };

    try {
      const res = await authFetch('/api/v1/coaching/philosophies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Save failed');
      }
      showToast('Philosophy saved!', 'success');
      await loadPhilosophies();
    } catch (e) {
      showToast('Failed saving philosophy: ' + e.message, 'error');
    }
  });

  document.getElementById('btn-activate-philosophy').addEventListener('click', async () => {
    if (!selectedPhilosophyId) return;
    try {
      const res = await authFetch(`/api/v1/coaching/philosophies/${selectedPhilosophyId}/activate`, { method: 'POST' });
      if (!res.ok) throw new Error('Activation failed');
      showToast('Philosophy activated!', 'success');
      await loadPhilosophies();
    } catch (e) {
      showToast('Failed activating philosophy: ' + e.message, 'error');
    }
  });

  // --- Critique Analysis ---
  document.getElementById('btn-analyze').addEventListener('click', async () => {
    const btn = document.getElementById('btn-analyze');
    const errBox = document.getElementById('critique-error');
    errBox.style.display = 'none';
    btn.disabled = true;
    btn.textContent = 'Analyzing...';

    try {
      const res = await authFetch('/api/v1/coaching/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail = err.detail || res.statusText;
        errBox.style.display = 'block';
        errBox.innerHTML = `<strong>Unable to run critique:</strong> ${escapeHtml(detail)}<br><br>💡 <em>Tip:</em> Check <a href="/config" style="color:var(--accent); text-decoration:underline;">Settings</a> to configure your AI provider or load workouts.`;
        return;
      }
      const critique = await res.json();
      renderCritique(critique);
      showToast('Workout critique generated!', 'success');
    } catch (e) {
      errBox.style.display = 'block';
      errBox.textContent = 'Analysis request failed: ' + e.message;
    } finally {
      btn.disabled = false;
      btn.textContent = 'Analyze Latest Workout';
    }
  });

  async function loadRecentCritique() {
    try {
      const res = await authFetch('/api/v1/coaching/critiques/recent?limit=1');
      if (!res.ok) return;
      const list = await res.json();
      if (list.length > 0) renderCritique(list[0]);
    } catch (e) {
      console.error('Error loading recent critique:', e);
    }
  }

  function renderCritique(c) {
    document.getElementById('critique-error').style.display = 'none';
    document.getElementById('critique-container').style.display = 'flex';
    document.getElementById('critique-score').textContent = Math.round(c.adherence_score);
    document.getElementById('critique-provider-tag').textContent = `Provider: ${c.provider_used} • ${new Date(c.created_at).toLocaleDateString()}`;
    document.getElementById('critique-summary').innerHTML = formatMarkdown(c.summary_markdown);

    const recsContainer = document.getElementById('critique-recommendations');
    recsContainer.innerHTML = '';
    (c.recommendations || []).forEach((r) => {
      const item = document.createElement('div');
      item.className = 'recommendation-item';
      item.textContent = r;
      recsContainer.appendChild(item);
    });
  }

  // --- Forward Schedule Plan ---
  document.getElementById('btn-generate-plan').addEventListener('click', async () => {
    const goal = document.getElementById('plan-goal').value.trim();
    const btn = document.getElementById('btn-generate-plan');
    const errBox = document.getElementById('plan-error');
    errBox.style.display = 'none';

    if (!goal) {
      showToast('Please specify an athlete goal.', 'error');
      return;
    }

    btn.disabled = true;
    btn.textContent = 'Generating Plan...';
    try {
      const res = await authFetch('/api/v1/coaching/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_goal: goal,
          horizon_days: parseInt(document.getElementById('plan-horizon').value, 10),
          available_days_per_week: parseInt(document.getElementById('plan-days').value, 10),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        errBox.style.display = 'block';
        errBox.textContent = 'Planning error: ' + (err.detail || res.statusText);
        return;
      }
      const plan = await res.json();
      renderPlan(plan);
      showToast('Training plan generated!', 'success');
    } catch (e) {
      errBox.style.display = 'block';
      errBox.textContent = 'Planning failed: ' + e.message;
    } finally {
      btn.disabled = false;
      btn.textContent = 'Generate Training Plan';
    }
  });

  async function loadActivePlan() {
    try {
      const res = await authFetch('/api/v1/coaching/plans/active');
      if (!res.ok) return;
      const plan = await res.json();
      renderPlan(plan);
    } catch (_) {}
  }

  async function toggleScheduledCompletion(workoutId, isCompleted, cardEl, checkboxEl) {
    checkboxEl.disabled = true;
    try {
      const res = await authFetch(`/api/v1/coaching/scheduled-workouts/${workoutId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_completed: isCompleted }),
      });
      if (!res.ok) throw new Error('Failed to update completion status');
      cardEl.classList.toggle('completed', isCompleted);
    } catch (err) {
      checkboxEl.checked = !isCompleted;
      showToast(err.message, 'error');
    } finally {
      checkboxEl.disabled = false;
    }
  }

  function renderPlan(p) {
    document.getElementById('active-plan-container').style.display = 'flex';
    document.getElementById('plan-goal-title').textContent = p.target_goal;
    document.getElementById('plan-summary').innerHTML = formatMarkdown(p.summary_markdown);

    const grid = document.getElementById('calendar-grid');
    grid.innerHTML = '';

    (p.scheduled_workouts || []).forEach((w) => {
      const card = document.createElement('div');
      card.className = `workout-card ${w.is_completed ? 'completed' : ''}`;
      const discClass = `discipline-${String(w.discipline || 'rest').replace('outdoor_', '').replace('indoor_', '').replace('erg_', '')}`;

      const details = [];
      if (w.planned_duration_min > 0) details.push(`${w.planned_duration_min} min`);
      if (w.target_distance_m) details.push(`${(w.target_distance_m / 1000).toFixed(1)} km`);
      if (w.target_zone) details.push(w.target_zone);
      if (w.target_rpe) details.push(`RPE ${w.target_rpe}`);

      let strengthHtml = '';
      if (w.strength_exercises && w.strength_exercises.length > 0) {
        const exNames = w.strength_exercises.map((e) => e.name || e.exercise_name || '').filter(Boolean).join(', ');
        if (exNames) {
          strengthHtml = `<div style="font-size: 11px; color: var(--purple);">Exercises: ${escapeHtml(exNames)}</div>`;
        }
      }

      card.innerHTML = `
        <div class="workout-header">
          <div class="workout-title">
            <input type="checkbox" class="toggle-complete-chk" ${w.is_completed ? 'checked' : ''} aria-label="Mark completed" />
            <span class="discipline-tag ${escapeHtml(discClass)}">${escapeHtml(w.discipline)}</span>
            <span>${escapeHtml(w.title)}</span>
          </div>
          <span style="font-size: 12px; color: var(--text-muted); font-weight: 600;">${escapeHtml(w.target_date)}</span>
        </div>
        <div class="workout-meta">
          ${details.map((d) => `<span>• ${escapeHtml(d)}</span>`).join(' ')}
        </div>
        ${strengthHtml}
        ${w.notes ? `<div class="workout-notes">${escapeHtml(w.notes)}</div>` : ''}
      `;

      const chk = card.querySelector('.toggle-complete-chk');
      chk.addEventListener('change', () => toggleScheduledCompletion(w.id, chk.checked, card, chk));
      grid.appendChild(card);
    });
  }

  window.addEventListener('DOMContentLoaded', () => {
    Promise.all([loadProviders(), loadPhilosophies(), loadActivePlan(), loadRecentCritique()]);
  });
})();
