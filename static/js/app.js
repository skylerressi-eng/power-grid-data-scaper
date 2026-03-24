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
  citySelect.innerHTML = '<option value="">— Select City —</option>';
  citySelect.disabled = true;
  analyzeBtn.disabled = true;

  if (!state) return;

  try {
    const res = await fetch(`/api/cities?state=${encodeURIComponent(state)}`);
    const cities = await res.json();
    if (!Array.isArray(cities)) throw new Error(cities.error || 'Unknown error');
    cities.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      citySelect.appendChild(opt);
    });
    citySelect.disabled = false;
  } catch (e) {
    showError('Failed to load cities: ' + e.message);
  }
});

// ── City change → enable button ───────────────────────────────────────────
citySelect.addEventListener('change', () => {
  analyzeBtn.disabled = !citySelect.value;
});

// ── Analyze button ────────────────────────────────────────────────────────
analyzeBtn.addEventListener('click', async () => {
  const state = stateSelect.value;
  const city  = citySelect.value;
  if (!state || !city) return;

  setLoading(true);
  hideError();
  resultsDiv.classList.add('hidden');

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state, city }),
    });
    const data = await res.json();

    if (!res.ok || data.error) {
      throw new Error(data.error || `HTTP ${res.status}`);
    }

    renderResults(data);
    resultsDiv.classList.remove('hidden');
    resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {
    showError(e.message);
  } finally {
    setLoading(false);
  }
});

// ── Render all result sections ────────────────────────────────────────────
function renderResults(data) {
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

  // Charts
  renderGenMixChart(grid.generation_mix);
  renderDispatchChart(opt.dispatch_table);

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
}

function hideError() {
  errorBanner.classList.add('hidden');
}
