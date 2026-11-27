/* Coach3 Settings & Integrations Hub — CSP-Compliant, Secret-Safe, Diagnostics-Ready */
(function () {
  'use strict';

  const { escapeHtml, safeCopy, showToast, authFetch } = window.Coach3;

  const origin = window.location.origin;
  document.getElementById('polarCallbackUrl').textContent = origin + '/api/v1/integrations/polar/callback';
  document.getElementById('concept2CallbackUrl').textContent = origin + '/api/v1/integrations/concept2/callback';

  const providerState = {
    polar: { is_configured: false, decryption_error: false },
    concept2: { is_configured: false, decryption_error: false },
  };

  function checkQueryParams() {
    const params = new URLSearchParams(window.location.search);
    const status = params.get('status');
    const provider = params.get('provider');
    const message = params.get('message');
    const banner = document.getElementById('statusBanner');
    const text = document.getElementById('bannerText');

    if (status === 'connected') {
      banner.className = 'alert-banner alert-success';
      banner.style.display = 'flex';
      text.textContent = `Successfully connected to ${provider ? provider.toUpperCase() : 'service'}! Workout synchronization is now active.`;
      showToast('Connected successfully!', 'success');
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (status === 'error') {
      banner.className = 'alert-banner alert-error';
      banner.style.display = 'flex';
      text.textContent = `Connection error (${provider || 'OAuth'}): ${message || 'Authorization failed'}`;
      showToast('Authorization error encountered.', 'error');
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }

  document.getElementById('btnCloseBanner').addEventListener('click', () => {
    document.getElementById('statusBanner').style.display = 'none';
  });

  async function copyCallbackUrl(elementId) {
    const text = document.getElementById(elementId).textContent || '';
    try {
      await safeCopy(text);
      showToast('Callback URL copied to clipboard!', 'success');
    } catch (_) {
      showToast('Copy failed — please select and copy the URL manually.', 'error');
    }
  }

  document.getElementById('btnCopyPolarUrl').addEventListener('click', () => copyCallbackUrl('polarCallbackUrl'));
  document.getElementById('btnCopyConcept2Url').addEventListener('click', () => copyCallbackUrl('concept2CallbackUrl'));

  // --- Integration Credentials & Status ---
  async function loadConfigs() {
    try {
      const res = await authFetch('/api/v1/config/integrations');
      if (!res.ok) throw new Error('Failed to load configs');
      const configs = await res.json();

      configs.forEach((c) => {
        providerState[c.provider] = {
          is_configured: Boolean(c.is_configured),
          decryption_error: Boolean(c.decryption_error),
        };

        const badge = document.getElementById(`${c.provider}StatusBadge`);
        const idInput = document.getElementById(`${c.provider}ClientId`);
        const secInput = document.getElementById(`${c.provider}ClientSecret`);
        const warnBox = document.getElementById(`${c.provider}DecryptWarning`);

        if (c.decryption_error) {
          badge.className = 'badge badge-danger';
          badge.textContent = 'Key Mismatch — Re-enter';
          warnBox.style.display = 'block';
          idInput.placeholder = 'Re-enter Client ID (required)';
        } else {
          warnBox.style.display = 'none';
          if (c.is_connected) {
            badge.className = 'badge badge-success';
            badge.textContent = 'Connected';
          } else if (c.is_configured) {
            badge.className = 'badge badge-warning';
            badge.textContent = 'Configured (Not Linked)';
          } else {
            badge.className = 'badge badge-danger';
            badge.textContent = 'Unconfigured';
          }

          // NEVER put masked_client_id into .value — strictly placeholder!
          if (c.masked_client_id) {
            idInput.placeholder = `Saved: ${c.masked_client_id} (leave blank to keep)`;
          }
        }
        idInput.value = '';
        secInput.value = '';
      });
    } catch (err) {
      showToast('Error loading integration configurations: ' + err.message, 'error');
    }
  }

  async function saveCredentials(provider) {
    const cid = document.getElementById(`${provider}ClientId`).value.trim();
    const csec = document.getElementById(`${provider}ClientSecret`).value.trim();
    const redir = document.getElementById(`${provider}CallbackUrl`).textContent;
    const st = providerState[provider] || {};

    if (!csec) {
      showToast('Please enter a Client Secret.', 'error');
      return;
    }
    if (!cid && (!st.is_configured || st.decryption_error)) {
      showToast('Please enter both Client ID and Client Secret.', 'error');
      return;
    }

    try {
      const res = await authFetch(`/api/v1/config/integrations/${provider}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_id: cid || null,
          client_secret: csec,
          redirect_uri: redir,
        }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to save credentials');
      }
      showToast(`Saved ${provider.toUpperCase()} credentials successfully!`, 'success');
      await loadConfigs();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  async function connectProvider(provider) {
    try {
      const res = await authFetch(`/api/v1/integrations/${provider}/auth-url`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Could not generate auth URL');
      }
      const data = await res.json();
      window.location.href = data.auth_url;
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  async function verifyProvider(provider) {
    const diagDiv = document.getElementById(`${provider}Diag`);
    diagDiv.style.display = 'block';
    diagDiv.textContent = 'Pinging API and checking token status...';

    try {
      const res = await authFetch(`/api/v1/integrations/${provider}/verify`, { method: 'POST' });
      const data = await res.json();

      if (data.status === 'healthy') {
        const athlete = escapeHtml(data.athlete_name || 'Authenticated');
        const syncNote = data.last_sync_at
          ? ` • Last synced: ${escapeHtml(new Date(data.last_sync_at).toLocaleString())}`
          : '';
        diagDiv.innerHTML = `<span style="color:var(--success);">✓ Healthy connection</span>: ${athlete}${syncNote}`;
        showToast(`${provider.toUpperCase()} connection verified healthy!`, 'success');
      } else if (data.status === 'expired') {
        diagDiv.innerHTML = `<span style="color:var(--warning);">⚠️ Token expired</span>. Please click 'Connect' to re-authorize.`;
        showToast(`${provider.toUpperCase()} token expired.`, 'info');
      } else {
        const detail = escapeHtml(data.error_message || data.status);
        diagDiv.innerHTML = `<span style="color:var(--danger);">✗ Diagnostic check:</span> ${detail}`;
        showToast(`Diagnostic issue: ${data.error_message || data.status}`, 'error');
      }
      await loadConfigs();
    } catch (err) {
      diagDiv.textContent = 'Verification failed: ' + err.message;
      showToast(err.message, 'error');
    }
  }

  async function syncProvider(provider) {
    const diagDiv = document.getElementById(`${provider}Diag`);
    diagDiv.style.display = 'block';
    diagDiv.textContent = `Synchronizing latest workouts from ${provider.toUpperCase()}...`;
    showToast(`Starting ${provider.toUpperCase()} sync...`, 'info');

    try {
      const res = await authFetch(`/api/v1/integrations/${provider}/sync`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Sync failed');
      }
      const log = await res.json();
      if (log.status === 'success') {
        diagDiv.innerHTML = `<span style="color:var(--success);">✓ Sync successful:</span> Imported ${escapeHtml(log.items_imported)} new, ${escapeHtml(log.items_updated)} updated.`;
        showToast(`${provider.toUpperCase()} sync complete (${log.items_imported} new).`, 'success');
      } else {
        const msg = log.error_message ? ` — ${escapeHtml(log.error_message)}` : '';
        diagDiv.innerHTML = `<span style="color:var(--danger);">✗ Sync status: ${escapeHtml(log.status)}</span>${msg}`;
        showToast(`Sync ${log.status}: ${log.error_message || 'Check logs'}`, 'error');
      }
      await loadConfigs();
      loadDiagnostics();
    } catch (err) {
      diagDiv.textContent = 'Sync failed: ' + err.message;
      showToast(err.message, 'error');
    }
  }

  document.getElementById('btnSavePolar').addEventListener('click', () => saveCredentials('polar'));
  document.getElementById('btnConnectPolar').addEventListener('click', () => connectProvider('polar'));
  document.getElementById('btnVerifyPolar').addEventListener('click', () => verifyProvider('polar'));
  document.getElementById('btnSyncPolar').addEventListener('click', () => syncProvider('polar'));

  document.getElementById('btnSaveConcept2').addEventListener('click', () => saveCredentials('concept2'));
  document.getElementById('btnConnectConcept2').addEventListener('click', () => connectProvider('concept2'));
  document.getElementById('btnVerifyConcept2').addEventListener('click', () => verifyProvider('concept2'));
  document.getElementById('btnSyncConcept2').addEventListener('click', () => syncProvider('concept2'));

  // --- AI Inference Provider ---
  function toggleAiFields(keepModel) {
    const type = document.getElementById('aiProviderType').value;
    const endpointGroup = document.getElementById('aiEndpointGroup');
    const scannedGroup = document.getElementById('aiScannedModelsGroup');
    const keyGroup = document.getElementById('aiApiKeyGroup');
    const modelInput = document.getElementById('aiModelName');

    if (type === 'llama_cpp') {
      endpointGroup.style.display = 'flex';
      keyGroup.style.display = 'none';
      if (!keepModel) modelInput.value = 'qwen2.5-14b-instruct';
    } else {
      endpointGroup.style.display = 'none';
      if (scannedGroup) scannedGroup.style.display = 'none';
      keyGroup.style.display = 'flex';
      if (!keepModel) modelInput.value = 'gemini-2.5-flash';
    }
  }

  async function scanLocalModels() {
    const endpointUrl = document.getElementById('aiEndpointUrl').value.trim();
    const scanBtn = document.getElementById('btnScanLocalModels');
    const scannedGroup = document.getElementById('aiScannedModelsGroup');
    const selectEl = document.getElementById('aiScannedModels');
    const modelInput = document.getElementById('aiModelName');

    if (!endpointUrl) {
      showToast('Enter a llama.cpp endpoint URL first.', 'error');
      return;
    }

    scanBtn.disabled = true;
    scanBtn.textContent = 'Scanning…';
    try {
      const res = await authFetch('/api/v1/coaching/providers/local/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint_url: endpointUrl }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `Scan failed (HTTP ${res.status})`);
      }

      const models = Array.isArray(data.models) ? data.models : [];
      selectEl.innerHTML = '';
      if (models.length === 0) {
        scannedGroup.style.display = 'none';
        showToast('Connected, but no models were returned by /v1/models.', 'warning');
        return;
      }

      const currentModel = modelInput.value.trim();
      models.forEach((m) => {
        const opt = document.createElement('option');
        opt.value = m;
        opt.textContent = m;
        if (m === currentModel) opt.selected = true;
        selectEl.appendChild(opt);
      });

      scannedGroup.style.display = 'flex';
      if (!models.includes(currentModel)) {
        selectEl.value = models[0];
        modelInput.value = models[0];
      }
      showToast(`Found ${models.length} installed model(s).`, 'success');
    } catch (err) {
      showToast(err.message || 'Could not scan local models.', 'error');
    } finally {
      scanBtn.disabled = false;
      scanBtn.textContent = 'Scan Models';
    }
  }

  document.getElementById('btnScanLocalModels').addEventListener('click', scanLocalModels);
  document.getElementById('aiScannedModels').addEventListener('change', (e) => {
    if (e.target.value) {
      document.getElementById('aiModelName').value = e.target.value;
    }
  });

  document.getElementById('aiProviderType').addEventListener('change', () => toggleAiFields(false));

  async function loadAiProviders() {
    const badge = document.getElementById('aiStatusBadge');
    try {
      const res = await authFetch('/api/v1/coaching/providers');
      if (!res.ok) return;
      const providers = await res.json();
      const active = providers.find((p) => p.is_active) || providers[0];
      if (!active) {
        badge.className = 'badge badge-warning';
        badge.textContent = 'Unconfigured';
        return;
      }
      document.getElementById('aiProviderType').value = active.provider_type;
      toggleAiFields(true);
      document.getElementById('aiModelName').value = active.model_name || '';
      if (active.endpoint_url) {
        document.getElementById('aiEndpointUrl').value = active.endpoint_url;
      }
      badge.className = 'badge badge-success';
      badge.textContent = `Active: ${active.provider_type} (${active.model_name})`;
    } catch (_) {
      badge.textContent = 'Unavailable';
    }
  }

  async function saveAiProvider() {
    const type = document.getElementById('aiProviderType').value;
    const model = document.getElementById('aiModelName').value.trim();
    const key = document.getElementById('aiApiKey').value.trim();
    const endpoint =
      type === 'llama_cpp'
        ? document.getElementById('aiEndpointUrl').value.trim()
        : 'https://generativelanguage.googleapis.com';

    try {
      const res = await authFetch('/api/v1/coaching/providers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider_type: type,
          model_name: model,
          endpoint_url: endpoint,
          api_key: key || undefined,
          is_active: true,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to save AI provider');
      }
      const saved = await res.json();

      // Explicitly activate the newly saved provider
      const actRes = await authFetch(`/api/v1/coaching/providers/${saved.id}/activate`, {
        method: 'POST',
      });
      if (!actRes.ok) {
        throw new Error('Saved AI provider, but activation failed.');
      }

      document.getElementById('aiApiKey').value = '';
      showToast('AI provider saved & activated!', 'success');
      await loadAiProviders();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  async function testAiProvider() {
    const diag = document.getElementById('aiDiag');
    diag.style.display = 'block';
    diag.textContent = 'Testing active inference provider connectivity...';
    try {
      const res = await authFetch('/api/v1/coaching/providers');
      if (!res.ok) throw new Error('Could not fetch active provider');
      const providers = await res.json();
      const active = providers.find((p) => p.is_active);
      if (!active) {
        diag.textContent = 'No active provider selected. Please save one first.';
        return;
      }

      const testRes = await authFetch(`/api/v1/coaching/providers/${active.id}/test`, { method: 'POST' });
      const testData = await testRes.json();
      if (testData.status === 'healthy') {
        diag.innerHTML = `<span style="color:var(--success);">✓ Connected</span>: ${escapeHtml(testData.message || 'Model responding')} (${escapeHtml(testData.latency_ms || 0)}ms)`;
        showToast('AI provider verified healthy!', 'success');
      } else {
        diag.innerHTML = `<span style="color:var(--danger);">✗ Unreachable:</span> ${escapeHtml(testData.message || 'Check config')}`;
        showToast('AI provider unreachable.', 'error');
      }
    } catch (err) {
      diag.textContent = 'Test failed: ' + err.message;
      showToast(err.message, 'error');
    }
  }

  document.getElementById('btnSaveAi').addEventListener('click', saveAiProvider);
  document.getElementById('btnTestAi').addEventListener('click', testAiProvider);

  // --- Heart Rate Profile ---
  async function loadHrProfile() {
    try {
      const res = await authFetch('/api/v1/profile/heart-rate');
      if (!res.ok) return;
      const p = await res.json();
      document.getElementById('hrResting').value = p.resting_hr;
      document.getElementById('hrMax').value = p.max_hr;
      document.getElementById('z1Min').value = p.zone1_min;
      document.getElementById('z1Max').value = p.zone1_max;
      document.getElementById('z2Min').value = p.zone2_min;
      document.getElementById('z2Max').value = p.zone2_max;
      document.getElementById('z3Min').value = p.zone3_min;
      document.getElementById('z3Max').value = p.zone3_max;
      document.getElementById('z4Min').value = p.zone4_min;
      document.getElementById('z4Max').value = p.zone4_max;
      document.getElementById('z5Min').value = p.zone5_min;
      document.getElementById('z5Max').value = p.zone5_max;
    } catch (_) {}
  }

  document.getElementById('btnDefaultHr').addEventListener('click', () => {
    const m = parseInt(document.getElementById('hrMax').value, 10) || 185;
    document.getElementById('z1Min').value = Math.round(m * 0.5);
    document.getElementById('z1Max').value = Math.round(m * 0.6);
    document.getElementById('z2Min').value = Math.round(m * 0.6);
    document.getElementById('z2Max').value = Math.round(m * 0.7);
    document.getElementById('z3Min').value = Math.round(m * 0.7);
    document.getElementById('z3Max').value = Math.round(m * 0.8);
    document.getElementById('z4Min').value = Math.round(m * 0.8);
    document.getElementById('z4Max').value = Math.round(m * 0.9);
    document.getElementById('z5Min').value = Math.round(m * 0.9);
    document.getElementById('z5Max').value = m;
  });

  document.getElementById('btnSaveHr').addEventListener('click', async () => {
    const payload = {
      resting_hr: parseInt(document.getElementById('hrResting').value, 10),
      max_hr: parseInt(document.getElementById('hrMax').value, 10),
      zone1_min: parseInt(document.getElementById('z1Min').value, 10),
      zone1_max: parseInt(document.getElementById('z1Max').value, 10),
      zone2_min: parseInt(document.getElementById('z2Min').value, 10),
      zone2_max: parseInt(document.getElementById('z2Max').value, 10),
      zone3_min: parseInt(document.getElementById('z3Min').value, 10),
      zone3_max: parseInt(document.getElementById('z3Max').value, 10),
      zone4_min: parseInt(document.getElementById('z4Min').value, 10),
      zone4_max: parseInt(document.getElementById('z4Max').value, 10),
      zone5_min: parseInt(document.getElementById('z5Min').value, 10),
      zone5_max: parseInt(document.getElementById('z5Max').value, 10),
    };
    try {
      const res = await authFetch('/api/v1/profile/heart-rate', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const msg = Array.isArray(err.detail)
          ? err.detail.map((d) => d.msg).join('; ')
          : (err.detail || 'Validation failed');
        throw new Error(msg);
      }
      showToast('Heart rate zones saved & workout history recalculated!', 'success');
    } catch (err) {
      showToast('Failed to save HR profile: ' + err.message, 'error');
    }
  });

  // --- Athlete Timezone & Export ---
  async function loadPreferences() {
    try {
      const res = await authFetch('/api/v1/profile/preferences');
      if (!res.ok) return;
      const prefs = await res.json();
      const tz = prefs.timezone || 'UTC';
      document.getElementById('athleteTimezone').value = tz;
      document.getElementById('timezoneBadge').textContent = tz;
    } catch (_) {}
  }

  document.getElementById('btnDetectTimezone').addEventListener('click', () => {
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
      document.getElementById('athleteTimezone').value = tz;
    } catch (_) {
      document.getElementById('athleteTimezone').value = 'UTC';
    }
  });

  document.getElementById('btnSaveTimezone').addEventListener('click', async () => {
    const tz = document.getElementById('athleteTimezone').value.trim();
    if (!tz) return;
    try {
      const res = await authFetch('/api/v1/profile/preferences', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ timezone: tz }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Invalid timezone');
      }
      const saved = await res.json();
      document.getElementById('timezoneBadge').textContent = saved.timezone;
      showToast(`Timezone updated to ${saved.timezone}`, 'success');
    } catch (err) {
      showToast(err.message, 'error');
    }
  });

  document.getElementById('btnExportZip').addEventListener('click', () => {
    window.location.href = '/api/v1/export';
  });

  // --- System Health & Sync Diagnostics ---
  async function loadDiagnostics() {
    const badge = document.getElementById('diagHealthBadge');
    const grid = document.getElementById('diagSummaryGrid');
    const auditEl = document.getElementById('diagAuditContainer');
    try {
      const res = await authFetch('/api/v1/system/diagnostics');
      if (!res.ok) {
        badge.className = 'badge';
        badge.textContent = 'Unavailable';
        return;
      }
      const d = await res.json();
      if (!d.database_ok) {
        badge.className = 'badge badge-danger';
        badge.textContent = 'Database Issue';
      } else if (d.has_recent_sync_failures) {
        badge.className = 'badge badge-warning';
        badge.textContent = 'Recent Sync Warning';
      } else {
        badge.className = 'badge badge-success';
        badge.textContent = 'Healthy';
      }

      const nextSync = d.next_scheduled_sync_at
        ? new Date(d.next_scheduled_sync_at).toLocaleString()
        : 'Not scheduled';

      grid.innerHTML = `
        <div class="diag-metric">
          <div class="diag-metric-label">Database</div>
          <div class="diag-metric-value">${d.database_ok ? '✓ Connected' : '✗ Unreachable'}</div>
        </div>
        <div class="diag-metric">
          <div class="diag-metric-label">Schema Revision</div>
          <div class="diag-metric-value">${escapeHtml(d.alembic_revision || 'N/A')}</div>
        </div>
        <div class="diag-metric">
          <div class="diag-metric-label">Scheduler</div>
          <div class="diag-metric-value">${d.scheduler_running ? 'Running' : 'Stopped'}</div>
        </div>
        <div class="diag-metric">
          <div class="diag-metric-label">Next Sync</div>
          <div class="diag-metric-value">${escapeHtml(nextSync)}</div>
        </div>
      `;

      const logs = d.recent_sync_logs || [];
      if (!logs.length) {
        auditEl.innerHTML = '<p style="font-size:12px;color:var(--text-muted);">No sync history recorded yet.</p>';
        return;
      }

      const rows = logs
        .map((l) => {
          const statusClass = l.status === 'success' ? 'badge-success' : (l.status === 'running' ? 'badge-warning' : 'badge-danger');
          const started = l.started_at ? new Date(l.started_at).toLocaleString() : '—';
          return `
            <tr>
              <td>${escapeHtml(l.provider)}</td>
              <td><span class="badge ${statusClass}">${escapeHtml(l.status)}</span></td>
              <td>${escapeHtml(l.items_imported)} / ${escapeHtml(l.items_updated)}</td>
              <td>${escapeHtml(started)}</td>
              <td>${escapeHtml(l.error_message || '')}</td>
            </tr>
          `;
        })
        .join('');

      auditEl.innerHTML = `
        <table class="audit-table">
          <thead>
            <tr>
              <th>Provider</th>
              <th>Status</th>
              <th>New / Upd</th>
              <th>Started</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      `;
    } catch (_) {
      badge.textContent = 'Unavailable';
    }
  }

  document.getElementById('btnRefreshDiag').addEventListener('click', loadDiagnostics);

  // --- Demo Data ---
  document.getElementById('btnSeedDemo').addEventListener('click', async () => {
    try {
      showToast('Seeding sample workouts...', 'info');
      const res = await authFetch('/api/v1/admin/demo/seed', { method: 'POST' });
      if (!res.ok) throw new Error('Failed to seed demo data');
      const data = await res.json();
      showToast(`Seeded ${data.workouts_created} workouts and ${data.strength_sets_created} strength sets!`, 'success');
    } catch (err) {
      showToast(err.message, 'error');
    }
  });

  document.getElementById('btnResetDemo').addEventListener('click', async () => {
    if (!confirm('Are you sure you want to purge all demo workouts? Real data will be preserved.')) return;
    try {
      const res = await authFetch('/api/v1/admin/demo', { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to reset demo data');
      const data = await res.json();
      showToast(`Reset complete. Purged ${data.workouts_deleted} demo workout records.`, 'success');
    } catch (err) {
      showToast(err.message, 'error');
    }
  });

  // --- Boot ---
  checkQueryParams();
  loadConfigs();
  loadAiProviders();
  loadHrProfile();
  loadPreferences();
  loadDiagnostics();
})();
