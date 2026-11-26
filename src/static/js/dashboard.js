/* Coach3 Training Volume & Performance Dashboard — CSP-Compliant, XSS-Safe, Paginated */
(function () {
  'use strict';

  const { escapeHtml, showToast, authFetch } = window.Coach3;

  const PAGE_SIZE = 25;
  let currentWindow = '30d';
  let customStartDate = null;
  let customEndDate = null;
  let loadedWorkouts = [];
  let totalWorkoutsCount = 0;

  let zone2MacroChart = null;
  let vo2MacroChart = null;
  let zoneChart = null;
  let activeExpandedRowId = null;
  let activeDetailChart = null;
  let activeIntervalCharts = {};
  let cachedDetailData = {};
  let detailViewMode = 'continuous';

  function destroyIntervalCharts() {
    Object.values(activeIntervalCharts).forEach((ch) => {
      if (ch) ch.destroy();
    });
    activeIntervalCharts = {};
  }

  function formatMinSec(sec, includeTenths) {
    if (sec === null || sec === undefined || Number.isNaN(Number(sec))) return '—';
    const num = Number(sec);
    const m = Math.floor(num / 60);
    const rem = num % 60;
    const s = includeTenths ? rem.toFixed(1) : String(Math.floor(rem));
    return `${m}:${Number(s) < 10 ? '0' : ''}${s}`;
  }

  function buildWindowQuery() {
    if (customStartDate && customEndDate) {
      return `start_date=${encodeURIComponent(customStartDate)}&end_date=${encodeURIComponent(customEndDate)}`;
    }
    return `window=${encodeURIComponent(currentWindow)}`;
  }

  function buildWorkoutsUrl(offset) {
    return `/api/v1/workouts?limit=${PAGE_SIZE}&offset=${offset}&${buildWindowQuery()}`;
  }

  // Filter pill interactions
  document.querySelectorAll('.filter-pill[data-window]').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-pill[data-window]').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      currentWindow = btn.getAttribute('data-window');
      customStartDate = null;
      customEndDate = null;
      document.getElementById('filter-start-date').value = '';
      document.getElementById('filter-end-date').value = '';
      cachedDetailData = {};
      activeExpandedRowId = null;
      loadDashboardData();
    });
  });

  document.getElementById('btn-apply-dates').addEventListener('click', () => {
    const sVal = document.getElementById('filter-start-date').value;
    const eVal = document.getElementById('filter-end-date').value;
    if (!sVal || !eVal) {
      showToast('Please select both a start date and an end date.', 'error');
      return;
    }
    if (sVal > eVal) {
      showToast('Start date must be on or before end date.', 'error');
      return;
    }
    customStartDate = sVal;
    customEndDate = eVal;
    document.querySelectorAll('.filter-pill[data-window]').forEach((b) => b.classList.remove('active'));
    cachedDetailData = {};
    activeExpandedRowId = null;
    loadDashboardData();
  });

  async function fetchWorkoutsPage(offset, append) {
    const res = await authFetch(buildWorkoutsUrl(offset));
    if (!res.ok) return;
    const headerTotal = parseInt(res.headers.get('X-Total-Count') || '0', 10);
    const page = await res.json();
    if (append) {
      loadedWorkouts = loadedWorkouts.concat(page);
    } else {
      loadedWorkouts = page;
    }
    totalWorkoutsCount = Number.isFinite(headerTotal) && headerTotal >= loadedWorkouts.length
      ? headerTotal
      : loadedWorkouts.length;
    renderWorkoutsTable(loadedWorkouts);
  }

  document.getElementById('btn-load-more').addEventListener('click', async () => {
    const btn = document.getElementById('btn-load-more');
    btn.disabled = true;
    try {
      await fetchWorkoutsPage(loadedWorkouts.length, true);
    } finally {
      btn.disabled = false;
    }
  });

  async function loadDashboardData() {
    try {
      const queryStr = buildWindowQuery();
      const [macroRes, summaryRes, prsRes] = await Promise.all([
        authFetch(`/api/v1/analytics/dashboard?${queryStr}`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
        authFetch(`/api/v1/analytics/summary?${queryStr}`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
        authFetch(`/api/v1/analytics/prs?${queryStr}`).then((r) => (r.ok ? r.json() : [])).catch(() => []),
      ]);

      await fetchWorkoutsPage(0, false);

      if (summaryRes) {
        updateKPIs(summaryRes, macroRes);
        const isEmpty =
          (!summaryRes.cardio || summaryRes.cardio.total_duration_hours === 0) &&
          (!summaryRes.strength || (summaryRes.strength.effective_working_sets || 0) === 0);
        document.getElementById('emptyNotice').style.display = isEmpty ? 'flex' : 'none';
        renderHRZoneDistribution(summaryRes.cardio);
      }

      if (macroRes) {
        renderCardioMacroVolume(macroRes.cardio);
        renderResistanceMuscleTable(macroRes.resistance);
      }

      renderPRShowcase(prsRes);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    }
  }

  function updateKPIs(data, macroData) {
    document.getElementById('kpi-duration').textContent = `${data.total_duration_hours || 0}h`;
    document.getElementById('kpi-zone2').textContent = `${data.zone2_duration_hours || 0}h`;
    document.getElementById('kpi-zone2-sub').textContent = `${data.zone2_percentage || 0}% of cardio`;

    const vo2Min = macroData && macroData.cardio ? macroData.cardio.zone5_minutes : 0;
    const z4Min = macroData && macroData.cardio ? macroData.cardio.zone4_minutes || 0 : 0;
    const z5Pct = macroData && macroData.cardio ? macroData.cardio.zone5_percentage : 0;
    document.getElementById('kpi-vo2max').textContent = `${Math.round(vo2Min)}m`;
    document.getElementById('kpi-vo2max-sub').textContent = `Z5 (${z5Pct}%) · Z4: ${Math.round(z4Min)}m`;

    const runKm = data.cardio ? data.cardio.outdoor_run_km || 0 : 0;
    document.getElementById('kpi-run').textContent = `${(runKm * 0.621371).toFixed(1)} mi`;

    const rowM = data.cardio ? data.cardio.erg_row_meters || 0 : 0;
    const bikeM = data.cardio ? data.cardio.erg_bike_meters || 0 : 0;
    document.getElementById('kpi-erg').textContent = `${(rowM + bikeM).toLocaleString()} m`;

    document.getElementById('kpi-sets').textContent = (data.strength ? data.strength.effective_working_sets : 0) || 0;
  }

  function buildSingleCardioGoalChart(canvasId, existingChart, trendLabels, barLabel, barColor, values, goalVal, goalLabel, goalColor) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return existingChart;
    const ctx = canvas.getContext('2d');
    if (existingChart) existingChart.destroy();

    const maxBar = Math.max(...values, 0);
    const suggestedMax = Math.max(goalVal * 1.2, maxBar * 1.15);

    return new Chart(ctx, {
      type: 'bar',
      data: {
        labels: trendLabels,
        datasets: [
          { label: barLabel, data: values, backgroundColor: barColor, borderRadius: 6, order: 2 },
          {
            type: 'line',
            label: goalLabel,
            data: trendLabels.map(() => goalVal),
            borderColor: goalColor,
            borderWidth: 2,
            borderDash: [6, 5],
            pointRadius: 0,
            fill: false,
            order: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
          tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.raw} mins` } },
        },
        scales: {
          x: { ticks: { color: '#94a3b8' }, grid: { display: false } },
          y: {
            min: 0,
            suggestedMax,
            ticks: { color: '#94a3b8' },
            grid: { color: '#1f293d' },
            title: { display: true, text: 'Minutes / Week', color: '#64748b' },
          },
        },
      },
    });
  }

  function renderCardioMacroVolume(cardio) {
    if (!cardio) return;
    const z2Goal = cardio.zone2_weekly_goal_minutes ?? 120.0;
    const vo2Goal = cardio.vo2max_weekly_goal_minutes ?? 20.0;
    const z2Avg = cardio.zone2_avg_weekly_minutes ?? 0.0;
    const z4Total = cardio.zone4_minutes ?? 0.0;
    const vo2Avg = cardio.vo2max_avg_weekly_minutes ?? 0.0;

    document.getElementById('pill-cardio-z2').textContent = `${Math.round(cardio.zone2_minutes)}m total · ${z2Avg}m/wk avg`;
    document.getElementById('pill-goal-z2').textContent = `Goal: ${Math.round(z2Goal)}m/wk`;
    document.getElementById('pill-cardio-vo2').textContent = `Z5: ${Math.round(cardio.zone5_minutes)}m (${vo2Avg}m/wk) · Z4: ${Math.round(z4Total)}m`;
    document.getElementById('pill-goal-vo2').textContent = `Z5 Goal: ${Math.round(vo2Goal)}m/wk`;

    const trend =
      cardio.weekly_trend && cardio.weekly_trend.length > 0
        ? cardio.weekly_trend
        : [{ week_label: 'Current', zone2_hours: 0, zone2_minutes: 0, zone4_minutes: 0, zone5_minutes: 0 }];

    const labels = trend.map((t) => t.week_label);
    const z2Mins = trend.map((t) => Math.round((t.zone2_minutes !== undefined ? t.zone2_minutes : t.zone2_hours * 60) * 10) / 10);
    const z4Mins = trend.map((t) => Math.round((t.zone4_minutes || 0) * 10) / 10);
    const vo2Mins = trend.map((t) => Math.round((t.zone5_minutes || 0) * 10) / 10);

    zone2MacroChart = buildSingleCardioGoalChart(
      'zone2MacroChart',
      zone2MacroChart,
      labels,
      'Zone 2 Base (min)',
      '#10b981',
      z2Mins,
      z2Goal,
      `${Math.round(z2Goal)} min/wk Goal`,
      '#6ee7b7'
    );

    const vo2Canvas = document.getElementById('vo2MacroChart');
    if (vo2Canvas) {
      const vCtx = vo2Canvas.getContext('2d');
      if (vo2MacroChart) vo2MacroChart.destroy();
      const maxHigh = Math.max(...vo2Mins.map((v, i) => v + z4Mins[i]), 0);
      vo2MacroChart = new Chart(vCtx, {
        type: 'bar',
        data: {
          labels,
          datasets: [
            { label: 'VO2 Max Zone 5 (min)', data: vo2Mins, backgroundColor: '#f43f5e', borderRadius: 6, stack: 'highInt', order: 2 },
            { label: 'Threshold Zone 4 (min)', data: z4Mins, backgroundColor: 'rgba(245, 158, 11, 0.78)', borderRadius: 6, stack: 'highInt', order: 3 },
            {
              type: 'line',
              label: `${Math.round(vo2Goal)} min/wk Z5 Goal`,
              data: labels.map(() => vo2Goal),
              borderColor: '#fda4af',
              borderWidth: 2,
              borderDash: [6, 5],
              pointRadius: 0,
              fill: false,
              order: 1,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
            tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.raw} mins` } },
          },
          scales: {
            x: { stacked: true, ticks: { color: '#94a3b8' }, grid: { display: false } },
            y: {
              stacked: true,
              min: 0,
              suggestedMax: Math.max(vo2Goal * 1.2, maxHigh * 1.15),
              ticks: { color: '#94a3b8' },
              grid: { color: '#1f293d' },
              title: { display: true, text: 'Minutes / Week', color: '#64748b' },
            },
          },
        },
      });
    }
  }

  function renderResistanceMuscleTable(resistance) {
    const tbody = document.getElementById('muscle-table-body');
    if (!resistance || resistance.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No resistance sets recorded in this window.</td></tr>';
      document.getElementById('pill-total-sets').textContent = '0 Total Sets';
      return;
    }

    let totalSets = 0;
    tbody.innerHTML = resistance
      .map((m) => {
        totalSets += m.working_sets;
        const topWeightDisplay = m.top_weight_lbs ? `${escapeHtml(m.top_weight_lbs)} lbs × ${escapeHtml(m.top_reps)}` : '—';
        const topExDisplay = m.top_exercise_name || '—';
        const est1rmDisplay = m.estimated_1rm_lbs ? `~${escapeHtml(m.estimated_1rm_lbs)} lbs` : '—';
        const goalSets = m.weekly_goal_sets ?? (m.muscle_group === 'other' ? 0 : 10);
        const avgSets = m.weekly_avg_sets ?? 0;
        const pct = Math.min(100, Math.round(m.goal_progress_pct ?? (goalSets > 0 ? (avgSets / goalSets) * 100 : 0)));
        const barColor = pct >= 100 ? '#10b981' : '#a855f7';

        const goalCell =
          goalSets > 0
            ? `<div class="goal-progress-wrap">
                 <div class="goal-bar-track"><div class="goal-bar-fill" style="width:${pct}%; background:${barColor};"></div></div>
                 <span style="font-size:12px; font-weight:700; color:${pct >= 100 ? '#10b981' : 'var(--text)'};">${escapeHtml(avgSets)} / ${escapeHtml(goalSets)}</span>
               </div>`
            : `<span style="font-size:11px; color:var(--text-muted);">Fallback (${escapeHtml(avgSets)}/wk)</span>`;

        return `
          <tr>
            <td class="muscle-name">${escapeHtml(m.display_name)}</td>
            <td>${goalCell}</td>
            <td><span class="set-badge">${escapeHtml(m.working_sets)} sets</span></td>
            <td><span class="weight-tag">${topWeightDisplay}</span></td>
            <td style="color:var(--text-muted); font-size:12px;">${escapeHtml(topExDisplay)}</td>
            <td><span class="rm-tag">${est1rmDisplay}</span></td>
          </tr>
        `;
      })
      .join('');

    document.getElementById('pill-total-sets').textContent = `${totalSets} Total Sets`;
  }

  function renderHRZoneDistribution(cardio) {
    const ctx = document.getElementById('hrZoneChart').getContext('2d');
    const dist =
      cardio && cardio.zone_distribution_hours
        ? cardio.zone_distribution_hours
        : { zone1: 0, zone2: 0, zone3: 0, zone4: 0, zone5: 0 };
    const dataVals = [dist.zone1, dist.zone2, dist.zone3, dist.zone4, dist.zone5];
    const hasData = dataVals.some((v) => v > 0);
    if (zoneChart) zoneChart.destroy();

    zoneChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Zone 1 (Warmup)', 'Zone 2 (Aerobic Base)', 'Zone 3 (Tempo)', 'Zone 4 (Threshold)', 'Zone 5 (VO2 Max)'],
        datasets: [
          {
            data: hasData ? dataVals : [1, 1, 1, 1, 1],
            backgroundColor: hasData
              ? ['#64748b', '#10b981', '#38bdf8', '#f59e0b', '#f43f5e']
              : ['#1e293b', '#1e293b', '#1e293b', '#1e293b', '#1e293b'],
            borderWidth: 2,
            borderColor: '#131a29',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'right', labels: { color: '#94a3b8', font: { size: 11 } } } },
      },
    });
  }

  function renderPRShowcase(prs) {
    const container = document.getElementById('pr-list-container');
    if (!prs || prs.length === 0) {
      container.innerHTML = '<div class="empty-state">No personal records logged yet. Complete workouts to set initial PRs!</div>';
      return;
    }

    container.innerHTML = prs
      .map(
        (pr) => `
        <div class="pr-item">
          <div class="pr-info">
            <span class="pr-title">${escapeHtml(pr.title)}</span>
            <span class="pr-date">${escapeHtml(new Date(pr.achieved_at).toLocaleDateString())}</span>
          </div>
          <div class="pr-badge-wrap">
            <span class="pr-value">${escapeHtml(pr.record_display)}</span>
            ${pr.is_recent ? '<span class="recent-tag">Recent</span>' : ''}
          </div>
        </div>
      `
      )
      .join('');
  }

  function renderWorkoutsTable(workouts) {
    const tbody = document.getElementById('workouts-table-body');
    const countSpan = document.getElementById('recent-workouts-count');
    const paginationBar = document.getElementById('pagination-bar');

    if (!workouts || workouts.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No workouts in this window. Try a wider window or sync in Settings!</td></tr>';
      countSpan.textContent = '';
      paginationBar.style.display = 'none';
      return;
    }

    countSpan.textContent = `Showing ${workouts.length} of ${totalWorkoutsCount}`;
    paginationBar.style.display = workouts.length < totalWorkoutsCount ? 'flex' : 'none';

    tbody.innerHTML = workouts
      .map((w) => {
        const dt = new Date(w.start_time_utc);
        const dateStr = dt.toLocaleDateString([], { month: 'short', day: 'numeric' });
        const timeStr = dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        let badgeClass = 'badge-run';
        let badgeIcon = '🏃';
        if (w.discipline === 'indoor_row') {
          badgeClass = 'badge-row';
          badgeIcon = '🚣';
        } else if (w.discipline === 'erg_bike') {
          badgeClass = 'badge-bike';
          badgeIcon = '🚴';
        } else if (w.discipline === 'strength') {
          badgeClass = 'badge-strength';
          badgeIcon = '🏋️';
        }

        const durMins = Math.round((w.duration_sec || 0) / 60);
        let volStr = '—';
        if (w.distance_m && w.distance_m > 0) {
          volStr = w.discipline === 'outdoor_run' ? `${(w.distance_m / 1000).toFixed(2)} km` : `${Math.round(w.distance_m).toLocaleString()} m`;
        }

        const intervalBadge = w.is_interval_workout
          ? '<span style="font-size:10px; background:rgba(245,158,11,0.2); color:#f59e0b; padding:2px 5px; border-radius:4px; margin-left:6px;">Intervals</span>'
          : '';

        const wid = escapeHtml(w.id);
        return `
          <tr class="workout-row" id="row-${wid}" data-workout-id="${wid}">
            <td style="white-space:nowrap;">
              <span style="font-weight:600; color:var(--text);">${escapeHtml(dateStr)}</span>
              <span style="display:block; font-size:11px; color:var(--text-muted);">${escapeHtml(timeStr)}</span>
            </td>
            <td><span class="discipline-badge ${badgeClass}">${badgeIcon} ${escapeHtml(w.discipline.replace('_', ' '))}</span></td>
            <td><span class="workout-title-text" style="font-weight:700;">${escapeHtml(w.title)}</span>${intervalBadge}</td>
            <td>${escapeHtml(durMins)} min</td>
            <td>${escapeHtml(volStr)}</td>
            <td><span style="font-weight:600; color:var(--accent); font-size:12px;">${escapeHtml(w.primary_metric_label || '—')}</span></td>
            <td style="text-align:right;">
              <button type="button" class="btn-secondary" style="padding:4px 10px; font-size:11px;" id="btn-expand-${wid}">Inspect ▾</button>
            </td>
          </tr>
          <tr class="drawer-row" id="drawer-${wid}">
            <td colspan="7" class="drawer-cell">
              <div class="drawer-content" id="drawer-content-${wid}">
                <div style="color:var(--text-muted); font-size:13px; text-align:center; padding:20px;">Loading workout telemetry...</div>
              </div>
            </td>
          </tr>
        `;
      })
      .join('');

    tbody.querySelectorAll('tr.workout-row').forEach((tr) => {
      tr.addEventListener('click', () => {
        const wid = tr.getAttribute('data-workout-id');
        if (wid) toggleWorkoutExpansion(wid);
      });
    });
  }

  async function toggleWorkoutExpansion(workoutId) {
    const drawer = document.getElementById(`drawer-${workoutId}`);
    const row = document.getElementById(`row-${workoutId}`);
    const btn = document.getElementById(`btn-expand-${workoutId}`);
    if (!drawer || !row) return;

    if (drawer.classList.contains('active')) {
      drawer.classList.remove('active');
      row.classList.remove('expanded');
      if (btn) btn.textContent = 'Inspect ▾';
      activeExpandedRowId = null;
      if (activeDetailChart) {
        activeDetailChart.destroy();
        activeDetailChart = null;
      }
      destroyIntervalCharts();
      return;
    }

    if (activeExpandedRowId && activeExpandedRowId !== workoutId) {
      const prevDrawer = document.getElementById(`drawer-${activeExpandedRowId}`);
      const prevRow = document.getElementById(`row-${activeExpandedRowId}`);
      const prevBtn = document.getElementById(`btn-expand-${activeExpandedRowId}`);
      if (prevDrawer) prevDrawer.classList.remove('active');
      if (prevRow) prevRow.classList.remove('expanded');
      if (prevBtn) prevBtn.textContent = 'Inspect ▾';
      destroyIntervalCharts();
    }

    drawer.classList.add('active');
    row.classList.add('expanded');
    if (btn) btn.textContent = 'Close ▴';
    activeExpandedRowId = workoutId;
    await loadWorkoutDetail(workoutId);
  }

  async function loadWorkoutDetail(workoutId) {
    const container = document.getElementById(`drawer-content-${workoutId}`);
    try {
      if (!cachedDetailData[workoutId]) {
        const res = await authFetch(`/api/v1/workouts/${workoutId}/detail`);
        if (!res.ok) throw new Error('Could not fetch detail');
        cachedDetailData[workoutId] = await res.json();
      }
      renderDrawerContent(workoutId, cachedDetailData[workoutId]);
    } catch (err) {
      container.innerHTML = `<div style="color:var(--danger); font-size:13px; padding:15px;">Failed to load detail: ${escapeHtml(err.message)}</div>`;
    }
  }

  function renderPaceSourceBadge(paceSource) {
    const labels = {
      strokes: 'Pace source: Measured Concept2 strokes',
      speed_samples: 'Pace source: Measured Polar speed stream',
      gps: 'Pace source: Derived from GPS trackpoints',
      splits: 'Pace source: Measured split intervals',
      session_average: 'Pace source: Session average only (no continuous speed/GPS stream)',
      none: 'Pace source: None recorded',
    };
    const txt = labels[paceSource || 'none'] || `Pace source: ${paceSource}`;
    return `<div><span class="pace-source-pill">${escapeHtml(txt)}</span></div>`;
  }

  function renderStrengthSetsSection(strengthSets) {
    if (!strengthSets || strengthSets.length === 0) return '';
    const rows = strengthSets
      .map((s) => {
        const weightLabel = s.is_bodyweight
          ? s.added_weight_lbs && s.added_weight_lbs > 0
            ? `BW + ${s.added_weight_lbs} lbs`
            : 'Bodyweight'
          : `${s.weight_lbs} lbs`;
        const wuBadge = s.is_warmup
          ? '<span style="font-size:10px; color:var(--text-muted); background:#1e293b; padding:1px 6px; border-radius:4px; margin-left:6px;">Warmup</span>'
          : '';
        return `
          <tr>
            <td style="font-weight:600;">${escapeHtml(s.exercise_name)}${wuBadge}</td>
            <td><span class="strength-cat-pill">${escapeHtml(s.category)}</span></td>
            <td>#${escapeHtml(s.set_index)}</td>
            <td>${escapeHtml(s.reps_completed)}</td>
            <td style="color:var(--accent); font-weight:600;">${escapeHtml(weightLabel)}</td>
            <td style="color:var(--text-muted);">${s.rpe !== null && s.rpe !== undefined ? escapeHtml(s.rpe) : '—'}</td>
          </tr>
        `;
      })
      .join('');

    return `
      <div style="margin-top: 10px;">
        <h4 style="font-size:12px; color:var(--text-muted); text-transform:uppercase; margin-bottom:8px;">Logged Sets</h4>
        <div class="table-container">
          <table class="split-summary-table">
            <thead>
              <tr><th>Exercise</th><th>Category</th><th>Set</th><th>Reps</th><th>Load</th><th>RPE</th></tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>
    `;
  }

  function renderDrawerContent(workoutId, data) {
    const container = document.getElementById(`drawer-content-${workoutId}`);
    const isInterval = data.interval_consistency && data.interval_consistency.superimposed_curves.length > 0;
    const hasTimeSeries = data.time_series && data.time_series.length > 0;
    destroyIntervalCharts();
    if (activeDetailChart) {
      activeDetailChart.destroy();
      activeDetailChart = null;
    }

    let controlsHtml = '';
    if (isInterval) {
      const consist = data.interval_consistency;
      const badgeClass = consist.is_consistent ? 'consistent-yes' : 'consistent-no';
      const badgeText = consist.is_consistent
        ? `✓ Consistent (±${consist.pace_variance_pct}% split variance)`
        : `⚠️ Pacing Fade (±${consist.pace_variance_pct}% split variance)`;

      controlsHtml = `
        <div class="drawer-controls">
          <div class="mode-toggle-group">
            <button type="button" class="mode-btn ${detailViewMode === 'continuous' ? 'active' : ''}" data-mode="continuous">Timeline (HR &amp; Pace)</button>
            <button type="button" class="mode-btn ${detailViewMode === 'overlay' ? 'active' : ''}" data-mode="overlay">⚡ Multi-Set Curve Overlay</button>
          </div>
          <span class="consistency-badge ${badgeClass}">${escapeHtml(badgeText)}</span>
        </div>
      `;
    }

    const editorHtml = `
      <div class="notes-editor-card">
        <div style="font-size:11px; color:var(--accent); text-transform:uppercase; font-weight:700;">Title &amp; Workout Notes</div>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <input type="text" class="edit-workout-title" style="flex:1; min-width:200px;" value="${escapeHtml(data.title || '')}" placeholder="Workout title" />
          <button type="button" class="btn-primary btn-save-workout-meta" style="padding:8px 14px; font-size:12px;">Save</button>
        </div>
        <textarea class="edit-workout-notes" rows="2" placeholder="Add workout notes, cues, or conditions...">${escapeHtml(data.user_notes || '')}</textarea>
      </div>
    `;

    const chartHtml = hasTimeSeries || isInterval
      ? `${renderPaceSourceBadge(data.pace_source)}<div class="chart-container" style="height: 260px;"><canvas id="canvas-detail-${escapeHtml(workoutId)}"></canvas></div>`
      : '';

    const noTelemetryHtml =
      !hasTimeSeries && !isInterval && (!data.strength_sets || data.strength_sets.length === 0)
        ? '<div style="color:var(--text-muted); font-size:13px; padding:6px 0;">No continuous telemetry or logged strength sets recorded for this session.</div>'
        : '';

    container.innerHTML = `
      ${renderSessionSummaryAndZones(data)}
      ${editorHtml}
      ${renderStrengthSetsSection(data.strength_sets)}
      ${noTelemetryHtml}
      ${controlsHtml}
      ${chartHtml}
      ${renderRouteMapCard(workoutId, data)}
      ${renderSplitsTable(workoutId, data.splits, data.rest_distance_m)}
    `;

    // Wire mode toggle buttons
    container.querySelectorAll('.mode-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        detailViewMode = btn.getAttribute('data-mode') || 'continuous';
        renderDrawerContent(workoutId, cachedDetailData[workoutId]);
      });
    });

    // Wire inline workout title/notes editor
    const saveMetaBtn = container.querySelector('.btn-save-workout-meta');
    if (saveMetaBtn) {
      saveMetaBtn.addEventListener('click', async () => {
        const titleInput = container.querySelector('.edit-workout-title');
        const notesInput = container.querySelector('.edit-workout-notes');
        const newTitle = titleInput.value.trim();
        const newNotes = notesInput.value;
        saveMetaBtn.disabled = true;
        try {
          const res = await authFetch(`/api/v1/workouts/${workoutId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: newTitle || undefined, user_notes: newNotes }),
          });
          if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Update failed');
          }
          const updated = await res.json();
          cachedDetailData[workoutId].title = updated.title;
          cachedDetailData[workoutId].user_notes = updated.user_notes;
          const rowTitle = document.querySelector(`#row-${workoutId} .workout-title-text`);
          if (rowTitle) rowTitle.textContent = updated.title;
          showToast('Workout updated!', 'success');
        } catch (err) {
          showToast(err.message, 'error');
        } finally {
          saveMetaBtn.disabled = false;
        }
      });
    }

    // Wire GPX file upload
    const gpxInput = container.querySelector('.gpx-file-input');
    if (gpxInput) {
      gpxInput.addEventListener('change', () => uploadWorkoutGpx(workoutId, gpxInput));
    }

    // Wire interval split row clicks
    container.querySelectorAll('tr.split-clickable').forEach((tr) => {
      tr.addEventListener('click', () => {
        const idx = parseInt(tr.getAttribute('data-split-index') || '0', 10);
        toggleIntervalGraph(workoutId, idx);
      });
    });

    if (detailViewMode === 'overlay' && isInterval) {
      renderOverlayChart(workoutId, data.interval_consistency.superimposed_curves, data.discipline);
    } else if (hasTimeSeries) {
      renderContinuousDualAxisChart(workoutId, data.time_series, data.discipline);
    }
  }

  function renderSessionSummaryAndZones(data) {
    const stats = [];
    if (data.total_duration_sec) {
      const hrs = Math.floor(data.total_duration_sec / 3600);
      const mins = Math.floor((data.total_duration_sec % 3600) / 60);
      const secs = Math.floor(data.total_duration_sec % 60);
      const durFormatted =
        hrs > 0
          ? `${hrs}:${mins < 10 ? '0' : ''}${mins}:${secs < 10 ? '0' : ''}${secs}`
          : `${mins}:${secs < 10 ? '0' : ''}${secs}`;
      stats.push({ label: 'Duration', val: durFormatted, sub: data.discipline === 'indoor_row' ? 'Work time' : 'Elapsed' });
    }
    if (data.total_distance_m && data.total_distance_m > 0) {
      if (data.discipline === 'outdoor_run') {
        stats.push({ label: 'Distance', val: `${(data.total_distance_m * 0.000621371).toFixed(2)} mi`, sub: `${(data.total_distance_m / 1000).toFixed(2)} km` });
      } else {
        stats.push({ label: 'Distance', val: `${Math.round(data.total_distance_m).toLocaleString()} m`, sub: '' });
      }
    }
    if (data.discipline === 'outdoor_run' && data.avg_pace_sec_per_km) {
      stats.push({ label: 'Avg Pace', val: `${formatMinSec(data.avg_pace_sec_per_km * 1.609344, false)} /mi`, sub: `${formatMinSec(data.avg_pace_sec_per_km, false)} /km` });
    }
    if (data.avg_heart_rate || data.max_heart_rate) {
      stats.push({ label: 'Heart Rate', val: `${data.avg_heart_rate || '—'} bpm`, sub: data.max_heart_rate ? `Max ${data.max_heart_rate} bpm` : '' });
    }
    if (data.total_calories) {
      stats.push({ label: 'Calories', val: `${data.total_calories} kcal`, sub: '' });
    }
    if (data.elevation_gain_m !== null && data.elevation_gain_m !== undefined) {
      stats.push({ label: 'Elevation', val: `+${Math.round(data.elevation_gain_m)} m`, sub: `${Math.round(data.elevation_gain_m * 3.28084)} ft ascent` });
    }

    const summaryHtml = stats.length
      ? `<div class="detail-summary-grid">${stats
          .map(
            (s) => `
          <div class="detail-stat-box">
            <span class="detail-stat-label">${escapeHtml(s.label)}</span>
            <span class="detail-stat-value">${escapeHtml(s.val)}</span>
            ${s.sub ? `<span class="detail-stat-sub">${escapeHtml(s.sub)}</span>` : ''}
          </div>`
          )
          .join('')}</div>`
      : '';

    let zonesHtml = '';
    if (data.hr_zone_seconds) {
      const z = data.hr_zone_seconds;
      const totalZ = (z.zone1 || 0) + (z.zone2 || 0) + (z.zone3 || 0) + (z.zone4 || 0) + (z.zone5 || 0);
      if (totalZ > 0) {
        const zColors = [
          { key: 'zone1', label: 'Z1', color: '#94a3b8' },
          { key: 'zone2', label: 'Z2', color: '#10b981' },
          { key: 'zone3', label: 'Z3', color: '#38bdf8' },
          { key: 'zone4', label: 'Z4', color: '#f59e0b' },
          { key: 'zone5', label: 'Z5', color: '#f43f5e' },
        ];
        const denom = Math.max(totalZ, data.total_duration_sec || totalZ);
        const segments = zColors
          .map((zc) => {
            const secs = z[zc.key] || 0;
            const pct = (secs / denom) * 100;
            return pct > 0.3
              ? `<div style="width:${pct.toFixed(1)}%; background:${zc.color}; border-radius:4px;" title="${zc.label}: ${formatMinSec(secs, false)} (${Math.round(pct)}%)"></div>`
              : '';
          })
          .join('');
        const legend = zColors
          .map((zc) => {
            const secs = z[zc.key] || 0;
            const pct = Math.round((secs / denom) * 100);
            return `<span><strong style="color:${zc.color};">${zc.label}:</strong> ${formatMinSec(secs, false)} (${pct}%)</span>`;
          })
          .join('');
        zonesHtml = `
          <div class="zone-mini-card">
            <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase; font-weight:600;">Heart Rate Zones Breakdown</div>
            <div class="zone-mini-bar">${segments}</div>
            <div class="zone-mini-legend">${legend}</div>
          </div>
        `;
      }
    }

    return `${summaryHtml}${zonesHtml}`;
  }

  function renderRouteMapCard(workoutId, data) {
    const pts = data.route_points || [];
    if (data.discipline !== 'outdoor_run' && pts.length === 0) return '';

    const uploadControl = `
      <label class="gpx-upload-btn" title="Attach or update GPS route from a .gpx file">
        <span>📍</span> ${pts.length >= 2 ? 'Replace GPX' : 'Upload Polar Flow GPX'}
        <input type="file" class="gpx-file-input" accept=".gpx,application/gpx+xml" style="display:none;">
      </label>
    `;

    if (pts.length < 2) {
      return `
        <div class="route-card">
          <div class="route-card-header">
            <div class="route-card-title">🗺️ Run Route Map</div>
            ${uploadControl}
          </div>
          <div style="color:var(--text-muted); font-size:12px;">
            No GPS trackpoints stored for this run yet. Upload an exported <code>.gpx</code> file to render the route map.
          </div>
        </div>
      `;
    }

    const lats = pts.map((p) => p.latitude);
    const lons = pts.map((p) => p.longitude);
    const minLat = Math.min(...lats), maxLat = Math.max(...lats);
    const minLon = Math.min(...lons), maxLon = Math.max(...lons);
    const cosLat = Math.cos(((minLat + maxLat) / 2) * (Math.PI / 180));
    const dLatM = Math.max(10, (maxLat - minLat) * 111320);
    const dLonM = Math.max(10, (maxLon - minLon) * 111320 * cosLat);

    const W = 640, H = 260, PAD = 28;
    const scale = Math.min((W - PAD * 2) / dLonM, (H - PAD * 2) / dLatM);
    const offsetX = (W - dLonM * scale) / 2;
    const offsetY = (H - dLatM * scale) / 2;

    const proj = pts.map((p) => [
      (offsetX + (p.longitude - minLon) * 111320 * cosLat * scale).toFixed(1),
      (offsetY + (maxLat - p.latitude) * 111320 * scale).toFixed(1),
    ]);
    const polylinePoints = proj.map((xy) => `${xy[0]},${xy[1]}`).join(' ');
    const startXY = proj[0];
    const endXY = proj[proj.length - 1];

    const barMeters = dLonM > 1500 ? 500 : dLonM > 400 ? 200 : 100;
    const barPx = Math.max(30, Math.round(barMeters * scale));
    const barFeet = Math.round(barMeters * 3.28084);

    const elevText =
      data.elevation_gain_m !== null && data.elevation_gain_m !== undefined
        ? `Elevation: +${Math.round(data.elevation_gain_m)}m / -${Math.round(data.elevation_loss_m || 0)}m`
        : '';

    return `
      <div class="route-card">
        <div class="route-card-header">
          <div class="route-card-title">🗺️ Run Route Map <span style="font-size:11px; color:var(--text-muted); font-weight:500;">(${pts.length.toLocaleString()} GPS points)</span></div>
          ${uploadControl}
        </div>
        <div class="route-map-wrap">
          <svg viewBox="0 0 ${W} ${H}" style="width:100%; height:240px; display:block;" role="img" aria-label="GPS Route Map">
            <polyline points="${polylinePoints}" fill="none" stroke="rgba(56, 189, 248, 0.25)" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
            <polyline points="${polylinePoints}" fill="none" stroke="#38bdf8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="${startXY[0]}" cy="${startXY[1]}" r="6" fill="#10b981" stroke="#080d18" stroke-width="2"/>
            <rect x="${Number(endXY[0]) - 5}" y="${Number(endXY[1]) - 5}" width="10" height="10" rx="2" fill="#f43f5e" stroke="#080d18" stroke-width="2"/>
            <g transform="translate(16, ${H - 18})">
              <line x1="0" y1="0" x2="${barPx}" y2="0" stroke="#94a3b8" stroke-width="2"/>
              <text x="${barPx + 6}" y="3" fill="#94a3b8" font-size="10">${barMeters}m (${barFeet} ft)</text>
            </g>
            <text x="${W - 22}" y="22" fill="#94a3b8" font-size="11" font-weight="700" text-anchor="middle">N ▲</text>
          </svg>
        </div>
        <div class="route-map-meta">
          <span><span style="color:#10b981;">●</span> Start &nbsp; <span style="color:#f43f5e;">■</span> Finish</span>
          <span>${escapeHtml(elevText)}</span>
          <span>Bounds: ${minLat.toFixed(4)}, ${minLon.toFixed(4)}</span>
        </div>
      </div>
    `;
  }

  async function uploadWorkoutGpx(workoutId, inputEl) {
    const file = inputEl.files && inputEl.files[0];
    if (!file) return;
    try {
      const gpxXml = await file.text();
      const res = await authFetch(`/api/v1/workouts/${workoutId}/gpx`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gpx_xml: gpxXml }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to upload GPX');
      }
      const updatedDetail = await res.json();
      cachedDetailData[workoutId] = updatedDetail;
      renderDrawerContent(workoutId, updatedDetail);
      showToast('GPX route uploaded!', 'success');
    } catch (e) {
      showToast('GPX upload failed: ' + e.message, 'error');
    }
  }

  function renderContinuousDualAxisChart(workoutId, timeSeries, discipline) {
    const canvas = document.getElementById(`canvas-detail-${workoutId}`);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (activeDetailChart) {
      activeDetailChart.destroy();
      activeDetailChart = null;
    }

    const hrData = timeSeries.map((pt) => ({ x: pt.elapsed_sec, y: pt.heart_rate }));
    const paceData = timeSeries.map((pt) => ({ x: pt.elapsed_sec, y: pt.pace_sec }));
    const hasPace = timeSeries.some((pt) => pt.pace_sec !== null && pt.pace_sec !== undefined);
    const hasSpm = timeSeries.some((pt) => pt.cadence_spm !== null && pt.cadence_spm !== undefined);

    const datasets = [
      {
        label: 'Heart Rate (bpm)',
        data: hrData,
        borderColor: '#f43f5e',
        backgroundColor: 'rgba(244, 63, 94, 0.1)',
        yAxisID: 'yHR',
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.25,
        spanGaps: true,
      },
    ];

    const scales = {
      x: {
        type: 'linear',
        min: 0,
        ticks: { color: '#94a3b8', maxTicksLimit: 12, callback: (val) => formatMinSec(val, false) },
        grid: { display: false },
      },
      yHR: {
        type: 'linear',
        position: 'left',
        title: { display: true, text: 'Heart Rate (bpm)', color: '#f43f5e' },
        ticks: { color: '#f43f5e' },
        grid: { color: '#1f293d' },
      },
    };

    if (hasPace) {
      datasets.push({
        label: discipline === 'indoor_row' ? 'Split (/500m)' : 'Pace (/km)',
        data: paceData,
        borderColor: '#38bdf8',
        backgroundColor: 'rgba(56, 189, 248, 0.1)',
        yAxisID: 'yPace',
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.2,
        spanGaps: discipline === 'outdoor_run',
      });
      scales.yPace = {
        type: 'linear',
        position: 'right',
        reverse: true,
        title: { display: true, text: 'Pace (Faster ▴)', color: '#38bdf8' },
        ticks: { color: '#38bdf8', callback: (val) => formatMinSec(val, false) },
        grid: { display: false },
      };
    }

    if (hasSpm) {
      datasets.push({
        label: 'SPM',
        data: timeSeries.map((pt) => ({ x: pt.elapsed_sec, y: pt.cadence_spm })),
        borderColor: '#818cf8',
        yAxisID: 'ySPM',
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.1,
        spanGaps: false,
      });
      scales.ySPM = {
        type: 'linear',
        position: 'right',
        min: 0,
        title: { display: true, text: 'SPM', color: '#818cf8' },
        ticks: { color: '#818cf8' },
        grid: { display: false },
      };
    }

    activeDetailChart = new Chart(ctx, {
      type: 'line',
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        parsing: false,
        interaction: { mode: 'nearest', axis: 'x', intersect: false },
        plugins: {
          legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
          tooltip: {
            callbacks: {
              title: (items) => (items.length ? `Elapsed: ${formatMinSec(items[0].parsed.x, true)}` : ''),
              label: (c) => {
                const yVal = c.parsed ? c.parsed.y : null;
                if (yVal === null || yVal === undefined) return '';
                if (c.dataset.yAxisID === 'yHR') return `Heart Rate: ${yVal} bpm`;
                if (c.dataset.yAxisID === 'ySPM') return `SPM: ${yVal}`;
                if (discipline === 'outdoor_run') {
                  return `Pace: ${formatMinSec(yVal, false)}/km (${formatMinSec(yVal * 1.609344, false)}/mi)`;
                }
                return `Pace: ${formatMinSec(yVal, true)}`;
              },
            },
          },
        },
        scales,
      },
    });
  }

  function renderOverlayChart(workoutId, curves, discipline) {
    const canvas = document.getElementById(`canvas-detail-${workoutId}`);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (activeDetailChart) {
      activeDetailChart.destroy();
      activeDetailChart = null;
    }

    const colors = ['#38bdf8', '#10b981', '#f59e0b', '#a855f7', '#ec4899'];
    const datasets = [];
    let hasAnyPace = false;

    curves.forEach((c, idx) => {
      const color = colors[idx % colors.length];
      const hrPts = c.points.filter((p) => p.heart_rate != null).map((p) => ({ x: p.set_elapsed_sec, y: p.heart_rate }));
      if (hrPts.length) {
        datasets.push({ label: `Interval ${c.set_index} HR`, data: hrPts, borderColor: color, yAxisID: 'yHR', borderWidth: 2.5, pointRadius: 0, tension: 0.3 });
      }
      const pacePts = c.points.filter((p) => p.pace_sec != null && p.pace_sec > 0).map((p) => ({ x: p.set_elapsed_sec, y: p.pace_sec }));
      if (pacePts.length) {
        hasAnyPace = true;
        datasets.push({ label: `Interval ${c.set_index} Pace`, data: pacePts, borderColor: color, yAxisID: 'yPace', borderWidth: 1.8, borderDash: [5, 4], pointRadius: 0, tension: 0.25 });
      }
    });

    const scales = {
      x: { type: 'linear', min: 0, ticks: { color: '#94a3b8', callback: (v) => formatMinSec(v, false) }, grid: { color: '#1f293d' } },
      yHR: { type: 'linear', position: 'left', ticks: { color: '#f43f5e' }, title: { display: true, text: 'Heart Rate (bpm)', color: '#f43f5e' }, grid: { color: '#1f293d' } },
    };
    if (hasAnyPace) {
      scales.yPace = { type: 'linear', position: 'right', reverse: true, ticks: { color: '#38bdf8', callback: (v) => formatMinSec(v, false) }, grid: { display: false } };
    }

    activeDetailChart = new Chart(ctx, {
      type: 'line',
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        parsing: false,
        plugins: { legend: { labels: { color: '#94a3b8', font: { size: 11 } } } },
        scales,
      },
    });
  }

  function renderSplitsTable(workoutId, splits, restDistanceM) {
    if (!splits || splits.length === 0) return '';
    let workCounter = 0;
    const wid = escapeHtml(workoutId);

    const rows = splits
      .map((sp) => {
        const isWorkOrLap = sp.split_type === 'interval' || sp.split_type === 'work' || sp.split_type === 'lap';
        const isRest = sp.split_type === 'rest';
        let typeLabel = 'Rest';
        if (isWorkOrLap) {
          workCounter += 1;
          typeLabel = sp.split_type === 'lap' ? `Split ${workCounter}` : `Interval ${workCounter}`;
        }
        const hasGraph = isWorkOrLap && sp.samples && sp.samples.length > 1;
        const typeClass = isRest ? 'split-rest' : hasGraph ? 'split-work split-clickable' : 'split-work';
        const paceDisplay = sp.avg_pace_sec ? formatMinSec(sp.avg_pace_sec, true) : '—';
        const durStr = formatMinSec(sp.duration_sec, false);
        const hrParts = [];
        if (sp.avg_heart_rate) hrParts.push(`Avg ${sp.avg_heart_rate}`);
        if (sp.peak_heart_rate) hrParts.push(`Peak ${sp.peak_heart_rate}`);
        const hrDisplay = hrParts.length ? `${hrParts.join(' · ')} bpm` : '—';

        const labelHtml = hasGraph
          ? `${escapeHtml(typeLabel)} <span style="font-size:10px; color:var(--accent); font-weight:600; margin-left:6px;" id="int-btn-${wid}-${sp.split_index}">📈 Graph ▾</span>`
          : escapeHtml(typeLabel);

        let html = `
          <tr class="${typeClass}" id="int-row-${wid}-${sp.split_index}" data-split-index="${sp.split_index}">
            <td>${labelHtml}</td>
            <td>${escapeHtml(durStr)}</td>
            <td>${sp.distance_m > 0 ? `${Math.round(sp.distance_m).toLocaleString()}m` : '—'}</td>
            <td><strong>${escapeHtml(paceDisplay)}</strong></td>
            <td>${escapeHtml(hrDisplay)}</td>
            <td>${sp.avg_power_watts ? `${Math.round(sp.avg_power_watts)}W` : '—'}</td>
          </tr>
        `;
        if (hasGraph) {
          html += `
            <tr id="int-drawer-${wid}-${sp.split_index}" style="display:none;">
              <td colspan="6" style="padding: 4px 8px 12px 8px;">
                <div class="interval-chart-box">
                  <div class="interval-chart-title">Workout Graph: ${escapeHtml(typeLabel)}</div>
                  <div style="height:220px; position:relative;">
                    <canvas id="canvas-interval-${wid}-${sp.split_index}"></canvas>
                  </div>
                </div>
              </td>
            </tr>
          `;
        }
        return html;
      })
      .join('');

    const restFooter =
      restDistanceM && restDistanceM > 0
        ? `<div style="font-size:11px; color:var(--text-muted); margin-top:6px;">Rest / recovery distance: ${Math.round(restDistanceM).toLocaleString()}m</div>`
        : '';

    return `
      <div style="margin-top: 10px;">
        <h4 style="font-size:12px; color:var(--text-muted); text-transform:uppercase;">Split &amp; Interval Breakdown</h4>
        <table class="split-summary-table">
          <thead>
            <tr><th>Interval / Split</th><th>Duration</th><th>Distance</th><th>Split / Pace</th><th>Heart Rate</th><th>Power</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
        ${restFooter}
      </div>
    `;
  }

  function toggleIntervalGraph(workoutId, splitIndex) {
    const drawer = document.getElementById(`int-drawer-${workoutId}-${splitIndex}`);
    const btn = document.getElementById(`int-btn-${workoutId}-${splitIndex}`);
    const chartKey = `${workoutId}-${splitIndex}`;
    if (!drawer) return;

    if (drawer.style.display !== 'none') {
      drawer.style.display = 'none';
      if (btn) btn.textContent = '📈 Graph ▾';
      if (activeIntervalCharts[chartKey]) {
        activeIntervalCharts[chartKey].destroy();
        delete activeIntervalCharts[chartKey];
      }
      return;
    }

    const data = cachedDetailData[workoutId];
    if (!data) return;
    const splitObj = data.splits.find((s) => s.split_index === splitIndex);
    if (!splitObj || !splitObj.samples || !splitObj.samples.length) return;

    drawer.style.display = 'table-row';
    if (btn) btn.textContent = '📈 Graph ▴';

    const canvas = document.getElementById(`canvas-interval-${workoutId}-${splitIndex}`);
    if (!canvas) return;
    const pts = splitObj.samples;
    activeIntervalCharts[chartKey] = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: {
        datasets: [
          {
            label: data.discipline === 'indoor_row' ? 'Pace (/500m)' : 'Pace (/km)',
            data: pts.map((p) => ({ x: p.set_elapsed_sec, y: p.pace_sec })),
            borderColor: '#38bdf8',
            yAxisID: 'yPace',
            borderWidth: 2,
            pointRadius: 0,
            spanGaps: true,
          },
          {
            label: 'Heart Rate',
            data: pts.map((p) => ({ x: p.set_elapsed_sec, y: p.heart_rate })),
            borderColor: '#f43f5e',
            yAxisID: 'yHR',
            borderWidth: 2,
            pointRadius: 0,
            spanGaps: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        parsing: false,
        scales: {
          x: { type: 'linear', min: 0, ticks: { color: '#94a3b8', callback: (v) => formatMinSec(v, false) } },
          yPace: { type: 'linear', position: 'left', reverse: true, ticks: { color: '#38bdf8', callback: (v) => formatMinSec(v, false) } },
          yHR: { type: 'linear', position: 'right', ticks: { color: '#f43f5e' }, grid: { display: false } },
        },
      },
    });
  }

  document.getElementById('btn-sync').addEventListener('click', async () => {
    const btn = document.getElementById('btn-sync');
    btn.disabled = true;
    btn.textContent = '⏳ Syncing...';
    try {
      cachedDetailData = {};
      const confRes = await authFetch('/api/v1/config/integrations');
      if (!confRes.ok) throw new Error('Could not fetch integration list');
      const configs = await confRes.json();
      const connected = configs.filter((c) => c.is_connected);
      if (!connected.length) {
        showToast('No connected providers found. Connect Polar or Concept2 in Settings.', 'info');
        return;
      }

      let totalNew = 0;
      let totalUpdated = 0;
      for (const prov of connected) {
        const syncRes = await authFetch(`/api/v1/integrations/${prov.provider}/sync`, { method: 'POST' });
        if (syncRes.ok) {
          const log = await syncRes.json();
          totalNew += log.items_imported || 0;
          totalUpdated += log.items_updated || 0;
        }
      }
      await loadDashboardData();
      showToast(`Sync complete! ${totalNew} new, ${totalUpdated} updated.`, 'success');
    } catch (err) {
      showToast('Sync error: ' + err.message, 'error');
    } finally {
      btn.textContent = '🔄 Sync Now';
      btn.disabled = false;
    }
  });

  loadDashboardData();
})();
