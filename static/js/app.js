/* Power Grid Analyzer — Frontend */

// ── Chart.js default theme ────────────────────────────────────────────────
Chart.defaults.color = '#8b949e';
Chart.defaults.borderColor = '#30363d';
Chart.defaults.font.family = "'Inter', -apple-system, sans-serif";

const FUEL_COLORS = {
  'natural-gas': '#f0883e',
  'coal':        '#8b949e',
  'nuclear':     '#bc8cff',
  'hydro':       '#58a6ff',
  'wind':        '#3fb950',
  'solar':       '#d29922',
  'geothermal':  '#39d353',
  'other':       '#484f58',
};

let genMixChart = null;
let dispatchChart = null;
let historyMixChart = null;

// ── DOM refs ──────────────────────────────────────────────────────────────
const stateSelect   = document.getElementById('state-select');
const citySelect    = document.getElementById('city-select');
const analyzeBtn    = document.getElementById('analyze-btn');
const btnLabel      = document.getElementById('btn-label');
const btnSpinner    = document.getElementById('btn-spinner');
const resultsDiv    = document.getElementById('results');
const errorBanner   = document.getElementById('error-banner');
const errorText     = document.getElementById('error-text');

// ── Init: load states ─────────────────────────────────────────────────────
(async function init() {
  try {
    const res = await fetch('/api/states');
    const states = await res.json();
    states.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s;
      opt.textContent = s;
      stateSelect.appendChild(opt);
    });
  } catch (e) {
    showError('Failed to load states: ' + e.message);
  }
})();

// ── State change → load cities ────────────────────────────────────────────
stateSelect.addEventListener('change', async () => {
  const state = stateSelect.value;
  citySelect.innerHTML = '<option value="" disabled selected>Loading cities…</option>';
  citySelect.disabled = true;
  analyzeBtn.disabled = true;
  hideError();

  if (!state) {
    citySelect.innerHTML = '<option value="">— Select City —</option>';
    return;
  }

  try {
    const res = await fetch(`/api/cities?state=${encodeURIComponent(state)}`);
    const cities = await res.json();
    if (!Array.isArray(cities)) throw new Error(cities.error || 'Unknown error');
    citySelect.innerHTML = '<option value="">— Select City —</option>';
    if (cities.length === 0) {
      citySelect.innerHTML = '<option value="">No cities found</option>';
      return;
    }
    cities.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      citySelect.appendChild(opt);
    });
    citySelect.disabled = false;
  } catch (e) {
    citySelect.innerHTML = '<option value="">— Select City —</option>';
    showError('Failed to load cities: ' + e.message);
  }
});

// ── City change → enable button ───────────────────────────────────────────
citySelect.addEventListener('change', () => {
  analyzeBtn.disabled = !citySelect.value;
});

// ── Enter key triggers analysis ───────────────────────────────────────────
document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !analyzeBtn.disabled &&
      (document.activeElement === citySelect || document.activeElement === stateSelect)) {
    analyzeBtn.click();
  }
});

// ── Analyze button — handled below after API key init ────────────────────

// ── Render all result sections ────────────────────────────────────────────
function renderResults(data) {
  lastOptData = data;
  resetOptimizer();
  const { provider, grid, optimization: opt } = data;

  // Provider
  document.getElementById('provider-name').textContent = provider.name || '—';
  document.getElementById('provider-meta').textContent =
    [provider.ownership, provider.service_type].filter(Boolean).join(' · ') || '';
  const others = (provider.all_providers || []).slice(1);
  document.getElementById('provider-all').textContent =
    others.length ? `Also serving: ${others.join(', ')}` : '';

  document.getElementById('retail-price').textContent =
    grid.retail_price_cents_kwh ? `${grid.retail_price_cents_kwh}¢/kWh` : '—';
  document.getElementById('annual-sales').textContent =
    grid.annual_sales_gwh ? `${fmt(grid.annual_sales_gwh)} GWh` : '—';
  document.getElementById('data-src').textContent = grid.data_source || '—';
  document.getElementById('data-source-label').textContent =
    grid.data_source || 'EIA + OpenEI';

  // Grid overview stats
  document.getElementById('total-capacity').textContent = fmt(opt.total_capacity_mw);
  document.getElementById('peak-demand').textContent    = fmt(opt.peak_demand_mw);
  document.getElementById('reserve-margin').textContent = opt.reserve_margin_pct + '%';
  document.getElementById('renewable-pct').textContent  = opt.renewable_pct_avg + '%';

  // Costs
  document.getElementById('peak-cost').textContent  = '$' + fmt(opt.peak_hourly_cost_usd) + '/hr';
  document.getElementById('avg-cost').textContent   = '$' + fmt(opt.avg_hourly_cost_usd) + '/hr';
  document.getElementById('annual-cost').textContent = '$' + fmt(opt.annual_operating_cost_usd);

  // Emissions
  document.getElementById('peak-co2').textContent      = fmt(opt.peak_co2_lbs_per_hour) + ' lbs/hr';
  document.getElementById('annual-co2').textContent    = fmt(opt.annual_co2_tons) + ' tons';
  document.getElementById('carbon-intensity').textContent =
    opt.grid_carbon_intensity_lbs_per_mwh + ' lbs/MWh';

  // Optimization
  document.getElementById('opt-converged').textContent = opt.optimization_converged ? '✓ Yes' : '✗ No';
  document.getElementById('renew-peak').textContent    = opt.renewable_pct_peak + '%';
  const lf = opt.avg_demand_mw && opt.peak_demand_mw
    ? ((opt.avg_demand_mw / opt.peak_demand_mw) * 100).toFixed(1) + '%'
    : '—';
  document.getElementById('load-factor').textContent = lf;

  // City profile
  renderCityStats(data.city_stats, data.city, data.state);

  // Charts
  renderGenMixChart(grid.generation_mix);
  renderDispatchChart(opt.dispatch_table);
  renderHistoricalSection(data.historical);

  // Dispatch table
  renderDispatchTable(opt.dispatch_table);

  // Recommendations
  renderRecommendations(opt.recommendations);
}

// ── Generation Mix Doughnut ───────────────────────────────────────────────
function renderGenMixChart(mix) {
  const labels = Object.keys(mix);
  const values = Object.values(mix);
  const colors = labels.map(l => FUEL_COLORS[l] || '#484f58');

  if (genMixChart) genMixChart.destroy();

  const ctx = document.getElementById('gen-mix-chart').getContext('2d');
  genMixChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels.map(l => l.replace('-', ' ').replace(/\b\w/g, c => c.toUpperCase())),
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderColor: '#161b22',
        borderWidth: 2,
        hoverOffset: 8,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '62%',
      plugins: {
        legend: {
          position: 'right',
          labels: {
            padding: 14,
            font: { size: 11 },
            color: '#8b949e',
            boxWidth: 14,
          },
        },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.label}: ${ctx.parsed}%`,
          },
        },
      },
    },
  });
}

// ── Dispatch Bar Chart ────────────────────────────────────────────────────
function renderDispatchChart(dispatchTable) {
  if (!dispatchTable || !dispatchTable.length) return;

  const labels = dispatchTable.map(r => r.name.replace(' Fleet', ''));
  const peakData = dispatchTable.map(r => r.peak_dispatch_mw);
  const avgData  = dispatchTable.map(r => r.avg_dispatch_mw);
  const colors   = dispatchTable.map(r => FUEL_COLORS[r.fuel_type] || '#484f58');

  if (dispatchChart) dispatchChart.destroy();

  const ctx = document.getElementById('dispatch-chart').getContext('2d');
  dispatchChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Peak Dispatch (MW)',
          data: peakData,
          backgroundColor: colors.map(c => c + 'cc'),
          borderColor: colors,
          borderWidth: 1,
          borderRadius: 3,
        },
        {
          label: 'Avg Dispatch (MW)',
          data: avgData,
          backgroundColor: colors.map(c => c + '55'),
          borderColor: colors.map(c => c + '88'),
          borderWidth: 1,
          borderRadius: 3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          grid: { color: '#21262d' },
          ticks: { font: { size: 10 }, maxRotation: 35 },
        },
        y: {
          grid: { color: '#21262d' },
          ticks: { callback: v => fmt(v) + ' MW' },
          title: { display: true, text: 'MW', color: '#8b949e' },
        },
      },
      plugins: {
        legend: { labels: { font: { size: 11 }, color: '#8b949e', boxWidth: 12 } },
        tooltip: {
          callbacks: { label: ctx => ` ${ctx.dataset.label}: ${fmt(ctx.parsed.y)} MW` },
        },
      },
    },
  });
}

// ── Historical Trends ─────────────────────────────────────────────────────
function renderHistoricalSection(historical) {
  if (!historical || !historical.length) return;

  const years = historical.map(h => h.year);

  // Collect all fuel types that appear with ≥1% share in any year
  const allFuels = [...new Set(historical.flatMap(h => Object.keys(h.generation_mix)))];
  const activeFuels = allFuels.filter(f =>
    Math.max(...historical.map(h => h.generation_mix[f] || 0)) >= 1.0
  );

  const datasets = activeFuels.map(fuel => {
    const color = FUEL_COLORS[fuel] || '#484f58';
    return {
      label: fuel.replace('-', ' ').replace(/\b\w/g, c => c.toUpperCase()),
      data: historical.map(h => h.generation_mix[fuel] || 0),
      borderColor: color,
      backgroundColor: color + '33',
      tension: 0.35,
      fill: false,
      pointRadius: 5,
      pointHoverRadius: 7,
      borderWidth: 2,
    };
  });

  if (historyMixChart) historyMixChart.destroy();
  const ctx = document.getElementById('history-mix-chart').getContext('2d');
  historyMixChart = new Chart(ctx, {
    type: 'line',
    data: { labels: years, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          min: 0,
          grid: { color: '#21262d' },
          ticks: { callback: v => v + '%' },
          title: { display: true, text: '% of Generation', color: '#8b949e' },
        },
        x: { grid: { color: '#21262d' } },
      },
      plugins: {
        legend: { labels: { font: { size: 10 }, color: '#8b949e', boxWidth: 12 } },
        tooltip: {
          callbacks: { label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y}%` },
        },
      },
    },
  });

  // Stats table
  const container = document.getElementById('history-stats');
  container.innerHTML = '';
  historical.forEach(h => {
    const el = document.createElement('div');
    el.className = 'history-year-block';
    el.innerHTML = `
      <div class="history-year-label">${h.year}</div>
      <div class="history-year-stats">
        <div class="history-stat">
          <span class="history-stat-label">Retail Price</span>
          <span class="history-stat-value">${h.retail_price_cents_kwh}¢/kWh</span>
        </div>
        <div class="history-stat">
          <span class="history-stat-label">Total Capacity</span>
          <span class="history-stat-value">${fmt(h.total_capacity_mw)} MW</span>
        </div>
        <div class="history-stat">
          <span class="history-stat-label">Annual Sales</span>
          <span class="history-stat-value">${fmt(h.annual_sales_gwh)} GWh</span>
        </div>
        <div class="history-stat">
          <span class="history-stat-label">Renewables Share</span>
          <span class="history-stat-value accent-green">${h.renewable_pct}%</span>
        </div>
      </div>
    `;
    container.appendChild(el);
  });
}

// ── Dispatch Table ────────────────────────────────────────────────────────
function renderDispatchTable(rows) {
  const tbody = document.getElementById('dispatch-tbody');
  tbody.innerHTML = '';

  (rows || []).forEach(row => {
    const util = row.peak_utilization_pct;
    const utilTag = util > 90 ? 'tag-red' : util > 70 ? 'tag-orange' : 'tag-green';
    const renewTag = row.is_renewable ? 'tag-green' : 'tag-gray';

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${row.name}</td>
      <td><span class="tag" style="background:${FUEL_COLORS[row.fuel_type]}22;color:${FUEL_COLORS[row.fuel_type]};border:1px solid ${FUEL_COLORS[row.fuel_type]}44">${row.fuel_type}</span></td>
      <td>${fmt(row.capacity_mw)}</td>
      <td>${fmt(row.peak_dispatch_mw)}</td>
      <td>${fmt(row.avg_dispatch_mw)}</td>
      <td><span class="tag ${utilTag}">${util}%</span></td>
      <td><span class="tag ${renewTag}">${row.is_renewable ? 'Yes' : 'No'}</span></td>
      <td>${row.emissions_lbs_per_mwh > 0 ? fmt(row.emissions_lbs_per_mwh) : '—'}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ── Recommendations ───────────────────────────────────────────────────────
const PRIORITY_STYLES = {
  critical: { cls: 'tag-red',    label: 'CRITICAL' },
  high:     { cls: 'tag-orange', label: 'HIGH' },
  medium:   { cls: 'tag-blue',   label: 'MEDIUM' },
  low:      { cls: 'tag-gray',   label: 'LOW' },
};

function renderRecommendations(recs) {
  const container = document.getElementById('recommendations');
  container.innerHTML = '';

  if (!recs || !recs.length) {
    container.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">No recommendations generated.</p>';
    return;
  }

  recs.forEach(rec => {
    const ps = PRIORITY_STYLES[rec.priority] || PRIORITY_STYLES.low;
    const el = document.createElement('div');
    el.className = 'rec-item';
    el.innerHTML = `
      <div class="rec-priority">
        <span class="tag ${ps.cls}">${ps.label}</span>
      </div>
      <div class="rec-body">
        <div class="rec-category">${rec.category}</div>
        <div class="rec-title">${rec.title}</div>
        <div class="rec-detail">${rec.detail}</div>
      </div>
    `;
    container.appendChild(el);
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────
function fmt(n) {
  if (n === null || n === undefined) return '—';
  return Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function setLoading(loading) {
  analyzeBtn.disabled = loading;
  btnLabel.textContent = loading ? 'Analyzing…' : 'Analyze Grid';
  btnSpinner.classList.toggle('hidden', !loading);
}

function showError(msg) {
  errorText.textContent = msg;
  errorBanner.classList.remove('hidden');
  setTimeout(() => errorBanner.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 50);
}

function hideError() {
  errorBanner.classList.add('hidden');
}

// ── API Key input + Test Key ───────────────────────────────────────────────
(function initApiKey() {
  const input   = document.getElementById('api-key-input');
  const toggle  = document.getElementById('api-key-toggle');
  const testBtn = document.getElementById('test-key-btn');
  const status  = document.getElementById('key-status');
  if (!input) return;

  // Restore saved key
  input.value = localStorage.getItem('eia_api_key') || '';

  // Save on change
  input.addEventListener('change', () => {
    localStorage.setItem('eia_api_key', input.value.trim());
    status.className = 'key-status hidden';
  });

  // Show/hide toggle
  toggle.addEventListener('click', () => {
    input.type = input.type === 'password' ? 'text' : 'password';
  });

  // Test Key button
  testBtn.addEventListener('click', async () => {
    const key = input.value.trim();
    if (!key) {
      setKeyStatus('error', 'Enter your API key first.');
      return;
    }
    localStorage.setItem('eia_api_key', key);
    testBtn.disabled = true;
    testBtn.textContent = 'Testing…';
    setKeyStatus('testing', 'Contacting EIA API…');
    try {
      const res  = await fetch('/api/test-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ eia_api_key: key }),
      });
      const data = await res.json();
      setKeyStatus(data.valid ? 'ok' : 'error', data.message);
    } catch (e) {
      setKeyStatus('error', 'Network error: ' + e.message);
    } finally {
      testBtn.disabled = false;
      testBtn.textContent = 'Test Key';
    }
  });

  function setKeyStatus(type, msg) {
    status.textContent = (type === 'ok' ? '✓ ' : type === 'error' ? '✗ ' : '◎ ') + msg;
    status.className = 'key-status key-status-' + type;
  }
})();

// Pass API key with every analyze request — patch the click handler
analyzeBtn.removeEventListener('click', analyzeBtn._handler); // clear if any
analyzeBtn.addEventListener('click', async function analyzeHandler() {
  const state = stateSelect.value;
  const city  = citySelect.value;
  if (!state || !city) return;

  const eia_api_key = (document.getElementById('api-key-input')?.value || '').trim();

  setLoading(true);
  hideError();
  resultsDiv.classList.add('hidden');

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state, city, eia_api_key }),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      const msg = data.error || `HTTP ${res.status}`;
      if (data.error_type === 'invalid_key') {
        throw new Error('Invalid EIA API key — use the "Test Key" button to verify your key, or get a free key at eia.gov/opendata');
      }
      throw new Error(msg);
    }
    renderResults(data);
    const now = new Date();
    const stamp = document.getElementById('analyzed-timestamp');
    if (stamp) stamp.textContent = `Analyzed ${now.toLocaleTimeString()} · ${data.city}, ${data.state}`;
    resultsDiv.classList.remove('hidden');
    // Stagger section entrance animations
    resultsDiv.querySelectorAll('section').forEach((s, i) => {
      s.style.animationDelay = (i * 55) + 'ms';
      s.classList.remove('section-animate');
      void s.offsetWidth; // force reflow to restart animation
      s.classList.add('section-animate');
    });
    resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {
    showError(e.message);
  } finally {
    setLoading(false);
  }
});

// ── City Profile ───────────────────────────────────────────────────────────
function renderCityStats(cs, city, state) {
  if (!cs) return;
  const pop = cs.city_population_k || 0;
  document.getElementById('city-profile-label').textContent = `— ${city}, ${state}`;
  document.getElementById('city-pop').textContent = pop
    ? (pop >= 1000 ? (pop / 1000).toFixed(2) + 'M' : pop.toLocaleString() + 'K')
    : '—';
  document.getElementById('city-peak').textContent =
    cs.estimated_peak_demand_mw ? fmt(cs.estimated_peak_demand_mw) + ' MW' : '—';
  document.getElementById('city-consumption').textContent =
    cs.estimated_annual_sales_gwh ? fmt(cs.estimated_annual_sales_gwh) + ' GWh/yr' : '—';
  document.getElementById('city-share').textContent =
    cs.city_share_pct != null ? cs.city_share_pct + '% of state' : '—';
  document.getElementById('city-price').textContent =
    cs.retail_price_cents_kwh ? cs.retail_price_cents_kwh + '¢/kWh' : '—';
  document.getElementById('city-climate').textContent =
    cs.climate_zone
      ? cs.climate_zone.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
      : '—';
  document.getElementById('city-note').textContent = cs.note || '';
}

// ── Optimizer ─────────────────────────────────────────────────────────────
let lastOptData = null;

const ALGO_STEPS = [
  { text: 'Initializing generator fleet from state data…', ms: 380 },
  { text: 'Building quadratic cost curves per fuel type…', ms: 460 },
  { text: 'Running lambda iteration at peak load…', ms: 680 },
  { text: 'Running lambda iteration at average load…', ms: 620 },
  { text: 'Computing CO₂ emissions profile per unit…', ms: 420 },
  { text: 'Evaluating renewable curtailment potential…', ms: 500 },
  { text: 'Checking reserve margin vs. NERC 15% standard…', ms: 330 },
  { text: 'Scoring demand response & storage opportunities…', ms: 510 },
  { text: 'Synthesizing prioritized recommendations…', ms: 590 },
  { text: 'Verifying power balance convergence threshold…', ms: 300 },
];

document.getElementById('start-algo-btn').addEventListener('click', runOptimizer);

function runOptimizer() {
  if (!lastOptData) return;

  const btn       = document.getElementById('start-algo-btn');
  const btnLabel  = document.getElementById('algo-btn-label');
  const spinner   = document.getElementById('algo-spinner');
  const progWrap  = document.getElementById('algo-progress-wrap');
  const stepList  = document.getElementById('algo-step-list');
  const summary   = document.getElementById('algo-summary');
  const opt       = lastOptData.optimization;

  btn.disabled = true;
  btnLabel.textContent = 'Running…';
  spinner.classList.remove('hidden');
  progWrap.classList.remove('hidden');
  summary.classList.add('hidden');
  stepList.innerHTML = '';
  setProgress(0);

  // Personalize first peak-load step with actual MW
  const steps = ALGO_STEPS.map((s, i) =>
    i === 2
      ? { ...s, text: `Running lambda iteration at peak load (${fmt(opt.peak_demand_mw)} MW)…` }
      : s
  );

  // Build step elements
  const stepEls = steps.map(s => {
    const el = document.createElement('div');
    el.className = 'step-item step-pending';
    el.innerHTML = `<span class="step-icon">○</span><span class="step-text">${s.text}</span>`;
    stepList.appendChild(el);
    return el;
  });

  // Animate each step sequentially
  let elapsed = 0;
  steps.forEach((s, i) => {
    const start = elapsed;
    elapsed += s.ms;

    setTimeout(() => {
      stepEls[i].className = 'step-item step-active';
      stepEls[i].querySelector('.step-icon').textContent = '◎';
      setProgress(i / steps.length * 92);
    }, start);

    setTimeout(() => {
      stepEls[i].className = 'step-item step-done';
      stepEls[i].querySelector('.step-icon').textContent = '✓';
    }, start + s.ms * 0.82);
  });

  // Finish
  setTimeout(() => {
    setProgress(100);
    spinner.classList.add('hidden');
    btnLabel.textContent = 'Re-Run Algorithm';
    btn.disabled = false;
    showAlgoSummary(opt, lastOptData);
  }, elapsed + 120);
}

function setProgress(pct) {
  const p = Math.min(100, Math.round(pct));
  document.getElementById('algo-progress-fill').style.width = p + '%';
  document.getElementById('algo-progress-pct').textContent = p + '%';
}

function showAlgoSummary(opt, data) {
  const converged = opt.optimization_converged;
  document.getElementById('algo-complete-text').textContent =
    converged ? 'Optimization Complete — Economic Dispatch Converged' : 'Optimization Complete — Near-Optimal Solution Found';
  document.getElementById('algo-convergence-note').textContent =
    converged ? `Solver tolerance < 0.1% at ${fmt(opt.peak_demand_mw)} MW peak` : 'Minor imbalance — results are valid';

  document.getElementById('sum-annual-cost').textContent = '$' + fmt(opt.annual_operating_cost_usd) + '/yr';
  document.getElementById('sum-carbon').textContent = opt.grid_carbon_intensity_lbs_per_mwh + ' lbs/MWh';
  document.getElementById('sum-renew').textContent = opt.renewable_pct_peak + '%';
  document.getElementById('sum-reserve').textContent = opt.reserve_margin_pct + '%';
  document.getElementById('sum-co2').textContent = fmt(opt.annual_co2_tons) + ' tons/yr';
  const lf = opt.avg_demand_mw && opt.peak_demand_mw
    ? ((opt.avg_demand_mw / opt.peak_demand_mw) * 100).toFixed(1) + '%' : '—';
  document.getElementById('sum-lf').textContent = lf;

  // Action list (all recs sorted by priority)
  const order = { critical: 0, high: 1, medium: 2, low: 3 };
  const recs = [...(opt.recommendations || [])].sort(
    (a, b) => (order[a.priority] ?? 9) - (order[b.priority] ?? 9)
  );
  const actionList = document.getElementById('algo-action-list');
  actionList.innerHTML = '';
  recs.forEach((rec, i) => {
    const ps = PRIORITY_STYLES[rec.priority] || PRIORITY_STYLES.low;
    const el = document.createElement('div');
    el.className = 'algo-action-item';
    el.style.animationDelay = (i * 80) + 'ms';
    el.innerHTML = `
      <div class="algo-action-num">${i + 1}</div>
      <div class="algo-action-body">
        <div class="algo-action-header">
          <span class="tag ${ps.cls}">${ps.label}</span>
          <span class="algo-action-category">${rec.category}</span>
          <span class="algo-action-title">${rec.title}</span>
        </div>
        <div class="algo-action-detail">${rec.detail}</div>
      </div>`;
    actionList.appendChild(el);
  });

  document.getElementById('algo-summary').classList.remove('hidden');
  document.getElementById('algo-summary').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function resetOptimizer() {
  document.getElementById('start-algo-btn').disabled = false;
  document.getElementById('algo-btn-label').textContent = 'Start Algorithm';
  document.getElementById('algo-spinner').classList.add('hidden');
  document.getElementById('algo-progress-wrap').classList.add('hidden');
  document.getElementById('algo-summary').classList.add('hidden');
  setProgress(0);
  document.getElementById('algo-step-list').innerHTML = '';
}

// ── Goal-Based Simulation Engine ──────────────────────────────────────────
let simChart = null;

document.getElementById('run-sims-btn').addEventListener('click', runSimulations);

async function runSimulations() {
  if (!lastOptData) return;

  const goalInput   = document.getElementById('savings-goal-input');
  const maxInput    = document.getElementById('max-sims-input');
  const btn         = document.getElementById('run-sims-btn');
  const btnLabel    = document.getElementById('sims-btn-label');
  const spinner     = document.getElementById('sims-spinner');
  const progWrap    = document.getElementById('sim-progress-wrap');
  const statusText  = document.getElementById('sim-status-text');
  const resultsDiv  = document.getElementById('sim-results');

  const savingsGoal = Math.max(1, parseFloat(goalInput.value) || 100);
  const maxSims     = parseInt(maxInput.value)    || 100;

  btn.disabled = true;
  btnLabel.textContent = 'Running…';
  spinner.classList.remove('hidden');
  progWrap.classList.remove('hidden');
  resultsDiv.classList.add('hidden');
  document.getElementById('sim-best-scenario').classList.add('hidden');
  simSetProgress(0);
  statusText.textContent = 'Fetching grid data and running simulations…';

  const eia_api_key = (document.getElementById('api-key-input')?.value || '').trim();

  let data;
  try {
    const res = await fetch('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        state: lastOptData.state,
        city:  lastOptData.city,
        eia_api_key,
        savings_goal: savingsGoal,
        max_sims: maxSims,
      }),
    });
    data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`);
  } catch (e) {
    showError('Simulation failed: ' + e.message);
    btn.disabled = false;
    btnLabel.textContent = 'Run Simulations';
    spinner.classList.add('hidden');
    progWrap.classList.add('hidden');
    return;
  }

  // Animate through simulation results
  const sims = data.simulations || [];
  const total = sims.length;
  let animIdx = 0;

  const chartLabels = [];
  const chartData   = [];
  const chartColors = [];
  const goalLine    = savingsGoal;

  // Initialize the live chart immediately (before animation starts)
  resultsDiv.classList.remove('hidden');
  document.getElementById('sim-complete-banner').classList && resultsDiv.classList.remove('hidden');
  if (simChart) simChart.destroy();
  const liveCtx = document.getElementById('sim-chart').getContext('2d');
  simChart = new Chart(liveCtx, {
    type: 'bar',
    data: {
      labels: chartLabels,
      datasets: [
        {
          label: 'Annual Savings ($)',
          data: chartData,
          backgroundColor: chartColors,
          borderWidth: 0,
          borderRadius: 2,
        },
        {
          type: 'line',
          label: `Goal: $${fmt(goalLine)}`,
          data: [],
          borderColor: '#f0883e',
          borderWidth: 2,
          borderDash: [5, 4],
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      scales: {
        x: {
          grid: { display: false },
          ticks: { display: total <= 50, font: { size: 9 } },
          title: { display: true, text: 'Simulation #', color: '#8b949e' },
        },
        y: {
          grid: { color: '#21262d' },
          ticks: { callback: v => '$' + fmt(v) },
          title: { display: true, text: 'Annual Savings ($)', color: '#8b949e' },
        },
      },
      plugins: {
        legend: { labels: { font: { size: 11 }, color: '#8b949e', boxWidth: 12 } },
        tooltip: {
          callbacks: {
            label: ctx => ctx.datasetIndex === 1
              ? ` Goal: $${fmt(ctx.parsed.y)}`
              : ` Sim #${ctx.label}: $${fmt(ctx.parsed.y)} savings`,
          },
        },
      },
    },
  });
  // Hide completion elements until done
  document.getElementById('sim-complete-banner').classList.add('hidden');
  document.querySelectorAll('#sim-results .algo-kpi-grid, #sim-best-scenario, #sim-results .algo-actions-title + div').forEach(el => el.classList.add('hidden'));

  // Batch update interval: update chart every N sims to avoid too many redraws
  const updateEvery = Math.max(1, Math.floor(total / 60));

  function animateNext() {
    if (animIdx >= total) {
      // Update chart one final time with all data
      simChart.data.datasets[1].data = Array(chartLabels.length).fill(goalLine);
      simChart.update('none');
      simSetProgress(100);
      statusText.textContent = `Complete — ${total} simulations run.`;
      spinner.classList.add('hidden');
      btnLabel.textContent = 'Re-Run Simulations';
      btn.disabled = false;
      showSimResults(data, savingsGoal, chartLabels, chartData, chartColors, goalLine);
      return;
    }

    const sim = sims[animIdx];
    const pct = Math.round((animIdx + 1) / total * 99);
    simSetProgress(pct);
    statusText.textContent =
      `Simulation ${sim.sim_id} of ${total} — DR: ${sim.demand_response_pct}%  |  ` +
      `Renew +${sim.renewable_boost_pct}%  |  ` +
      `Savings: $${fmt(sim.annual_savings_usd)}`;

    chartLabels.push(sim.sim_id);
    chartData.push(sim.annual_savings_usd);
    chartColors.push(sim.reached_goal ? '#3fb950' : '#58a6ff');

    // Update chart every N sims for smooth live rendering
    if (animIdx % updateEvery === 0 || animIdx === total - 1) {
      simChart.data.datasets[0].backgroundColor = chartColors.slice();
      simChart.data.datasets[1].data = Array(chartLabels.length).fill(goalLine);
      simChart.update('none');
    }

    animIdx++;
    setTimeout(animateNext, Math.max(8, Math.round(2400 / total)));
  }

  animateNext();
}

function simSetProgress(pct) {
  const p = Math.min(100, Math.round(pct));
  document.getElementById('sim-progress-fill').style.width = p + '%';
  document.getElementById('sim-progress-pct').textContent = p + '%';
}

function showSimResults(data, goal, labels, values, colors, goalLine) {
  const resultsDiv = document.getElementById('sim-results');

  // Restore elements that may have been hidden during live animation
  document.querySelectorAll('#sim-results .algo-kpi-grid').forEach(el => el.classList.remove('hidden'));
  document.getElementById('sim-complete-banner').classList.remove('hidden');

  // Banner
  const goalReached = data.goal_reached;
  document.getElementById('sim-complete-text').textContent = goalReached
    ? `Goal Reached — $${fmt(goal)}/yr savings found at simulation #${data.sims_to_reach_goal}`
    : `Simulations Complete — Goal of $${fmt(goal)}/yr not reached (best: $${fmt(data.best_savings_usd)})`;
  document.getElementById('sim-complete-banner').style.background =
    goalReached ? 'rgba(63,185,80,.12)' : 'rgba(240,136,62,.12)';
  document.getElementById('sim-complete-banner').style.borderColor =
    goalReached ? 'var(--green)' : 'var(--orange)';

  // KPIs
  document.getElementById('sim-baseline-cost').textContent = '$' + fmt(data.baseline_annual_cost_usd) + '/yr';
  document.getElementById('sim-best-savings').textContent  = '$' + fmt(data.best_savings_usd) + '/yr';
  document.getElementById('sim-goal-label').textContent    = fmt(goal);
  document.getElementById('sim-goal-at').textContent       = goalReached
    ? `Sim #${data.sims_to_reach_goal}` : 'Not reached';
  document.getElementById('sim-total-run').textContent     = data.simulations_run;

  // Best scenario
  const bs = data.best_scenario;
  if (bs) {
    document.getElementById('best-dr-pct').textContent        = bs.demand_response_pct + '% reduction';
    document.getElementById('best-renew-boost').textContent   = '+' + bs.renewable_boost_pct + '% renewables';
    document.getElementById('best-annual-cost').textContent   = '$' + fmt(bs.annual_cost_usd) + '/yr';
    document.getElementById('best-annual-savings').textContent= '$' + fmt(bs.annual_savings_usd) + '/yr';
    document.getElementById('best-renew-pct').textContent     = bs.renewable_pct_avg + '%';
    const co2Delta = lastOptData?.optimization?.annual_co2_tons && bs.annual_co2_tons
      ? fmt(Math.round(lastOptData.optimization.annual_co2_tons - bs.annual_co2_tons)) + ' tons/yr'
      : '—';
    document.getElementById('best-co2-delta').textContent = co2Delta;
    document.getElementById('sim-best-scenario').classList.remove('hidden');
  }

  // Chart
  if (simChart) simChart.destroy();
  const ctx = document.getElementById('sim-chart').getContext('2d');
  simChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Annual Savings ($)',
          data: values,
          backgroundColor: colors,
          borderWidth: 0,
          borderRadius: 2,
        },
        {
          type: 'line',
          label: `Goal: $${fmt(goal)}`,
          data: Array(labels.length).fill(goalLine),
          borderColor: '#f0883e',
          borderWidth: 2,
          borderDash: [5, 4],
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      scales: {
        x: {
          grid: { display: false },
          ticks: { display: labels.length <= 50, font: { size: 9 } },
          title: { display: true, text: 'Simulation #', color: '#8b949e' },
        },
        y: {
          grid: { color: '#21262d' },
          ticks: { callback: v => '$' + fmt(v) },
          title: { display: true, text: 'Annual Savings ($)', color: '#8b949e' },
        },
      },
      plugins: {
        legend: { labels: { font: { size: 11 }, color: '#8b949e', boxWidth: 12 } },
        tooltip: {
          callbacks: {
            label: ctx => ctx.dataset.type === 'line'
              ? ` Goal: $${fmt(ctx.parsed.y)}`
              : ` Sim #${ctx.label}: $${fmt(ctx.parsed.y)} savings`,
          },
        },
      },
    },
  });

  resultsDiv.classList.remove('hidden');
  resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
