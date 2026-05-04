/* ═══════════════════════════════════════════════════════════
   PhyloSuite — Frontend Application
   Three modules: Pipeline · Compare · Reports
═══════════════════════════════════════════════════════════ */
'use strict';

const API = '';
let state = {
  activeJob: null,
  jobs: [],
  selectedDB: 'ncbi',
  selectedAccessions: new Set(),
  compareSelected: new Set(),
  reportJobId: null,
  chart: null,
  pollTimer: null,
};

// ── INIT ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  loadJobs();
  initNav();
  initPipelineView();
  initDatabaseView();
  initCompareView();
  initReportView();
  setInterval(loadJobs, 8000);
});

// ── HEALTH CHECK ───────────────────────────────────────────
async function checkHealth() {
  try {
    const d = await api('/health');
    const tools = d.tools || {};
    const available = Object.values(tools).filter(t => t.available).length;
    const total = Object.keys(tools).length;
    const dot = document.getElementById('tsDot');
    const lbl = document.getElementById('tsLabel');
    if (available === total) { dot.className = 'ts-dot ok'; lbl.textContent = 'All tools ready'; }
    else if (available > 0)  { dot.className = 'ts-dot partial'; lbl.textContent = `${available}/${total} tools`; }
    else                     { dot.className = 'ts-dot error'; lbl.textContent = 'No tools found'; }
  } catch(e) {
    document.getElementById('tsLabel').textContent = 'Backend offline';
  }
}

// ── NAV ────────────────────────────────────────────────────
function initNav() {
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const view = btn.dataset.view;
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      document.getElementById(`view-${view}`).classList.add('active');
      document.getElementById('topbarTitle').textContent = btn.textContent.trim();
      if (view === 'compare')  renderCompareJobList();
      if (view === 'report')   renderReportJobList();
    });
  });
}

// ── JOB MANAGEMENT ─────────────────────────────────────────
async function loadJobs() {
  try {
    const d = await api('/api/jobs/');
    state.jobs = d.jobs || [];
    renderJobsMini();
    document.getElementById('jobCountBadge').textContent = `${state.jobs.length} job${state.jobs.length !== 1 ? 's' : ''}`;
  } catch(e) {}
}

function renderJobsMini() {
  const el = document.getElementById('jobsMini');
  const recent = state.jobs.slice(0, 8);
  el.innerHTML = recent.map(j => `
    <div class="job-mini-item" data-jid="${j.job_id}" title="${j.label}">
      <span class="jm-dot ${j.status}"></span>
      <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${j.label || j.job_id.slice(0,8)}</span>
    </div>`).join('');
  el.querySelectorAll('.job-mini-item').forEach(el => {
    el.addEventListener('click', () => openJobResults(el.dataset.jid));
  });
}

async function openJobResults(jobId) {
  const d = await api(`/api/jobs/${jobId}/full`);
  if (!d) return;
  state.activeJob = d;
  showResultsModal(d);
}

// ── PIPELINE VIEW ──────────────────────────────────────────
function initPipelineView() {
  // Tab switching
  document.querySelectorAll('[data-tab]').forEach(btn => {
    btn.addEventListener('click', () => {
      const bar = btn.closest('.tab-bar');
      bar.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tabId = btn.dataset.tab;
      const pane = document.getElementById(tabId);
      pane.closest('.card, .tab-pane')?.parentElement?.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      pane.classList.add('active');
    });
  });

  // Dropzone
  const dz = document.getElementById('plDropzone');
  const fi = document.getElementById('plFileInput');
  if (dz) {
    ['dragenter','dragover'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add('dragover'); }));
    ['dragleave','drop'].forEach(ev => dz.addEventListener(ev, e => {
      e.preventDefault(); dz.classList.remove('dragover');
      if (ev === 'drop' && e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]);
    }));
    fi.addEventListener('change', () => fi.files[0] && uploadFile(fi.files[0]));
  }

  // DB tabs within pipeline
  document.querySelectorAll('.db-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      btn.closest('.db-tabs').querySelectorAll('.db-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.selectedDB = btn.dataset.db;
      const boldOpts = document.getElementById('boldOpts');
      if (boldOpts) boldOpts.classList.toggle('hidden', state.selectedDB !== 'bold');
    });
  });

  document.getElementById('plBtnSearch')?.addEventListener('click', plSearch);
  document.getElementById('plBtnFetch')?.addEventListener('click', plFetch);
  document.getElementById('plDbQuery')?.addEventListener('keydown', e => { if (e.key === 'Enter') plSearch(); });
  document.getElementById('plBtnPaste')?.addEventListener('click', plPaste);
  document.getElementById('btnRunPipeline')?.addEventListener('click', runPipeline);
}

async function uploadFile(file) {
  const fd = new FormData();
  fd.append('file', file);
  showSeqInfo('plSeqInfo', { status: 'Uploading…' });
  try {
    const res = await fetch(`${API}/api/pipeline/upload`, { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    state.activeJob = { job_id: data.job_id, seq_info: data };
    showSeqInfo('plSeqInfo', data);
    document.getElementById('configCard').classList.remove('hidden');
    await loadJobs();
  } catch(e) { showSeqInfo('plSeqInfo', { error: e.message }); }
}

async function plSearch() {
  const query = document.getElementById('plDbQuery').value.trim();
  if (!query) return;
  const db = state.selectedDB;
  const resultsEl = document.getElementById('plSearchResults');
  resultsEl.classList.remove('hidden');
  resultsEl.innerHTML = '<p style="color:var(--text-dim);font-size:12px;padding:8px">Searching…</p>';
  document.getElementById('plFetchBar').classList.add('hidden');
  state.selectedAccessions.clear();

  let body = {
    database: db, query,
    db_type: document.getElementById('plDbType').value,
    max_results: document.getElementById('plDbMax').value,
  };
  if (db === 'bold') {
    body = {
      taxon: query, marker: document.getElementById('boldMarker')?.value || 'COI-5P',
      geo: document.getElementById('boldGeo')?.value || '', max_results: body.max_results,
    };
  }

  try {
    const endpoint = db === 'bold' ? '/api/database/bold-search' : '/api/database/search';
    const data = await apiPost(endpoint, body);
    renderSearchResults(data.results || [], resultsEl, 'plFetchBar', 'plFetchCount');
  } catch(e) {
    resultsEl.innerHTML = `<p style="color:var(--red);font-size:12px;padding:8px">Error: ${e.message}</p>`;
  }
}

async function plFetch() {
  const db = state.selectedDB;
  const isItBold = db === 'bold';
  showSeqInfo('plSeqInfoDb', { status: 'Fetching sequences…' });
  try {
    const endpoint = isItBold ? '/api/database/bold-fetch' : '/api/database/fetch';
    const body = isItBold
      ? { process_ids: [...state.selectedAccessions], marker: document.getElementById('boldMarker')?.value }
      : { accessions: [...state.selectedAccessions], database: db, db_type: document.getElementById('plDbType').value };
    const data = await apiPost(endpoint, body);
    state.activeJob = { job_id: data.job_id, seq_info: data };
    showSeqInfo('plSeqInfoDb', data);
    document.getElementById('configCard').classList.remove('hidden');
    await loadJobs();
  } catch(e) { showSeqInfo('plSeqInfoDb', { error: e.message }); }
}

async function plPaste() {
  const text = document.getElementById('plPasteArea').value.trim();
  if (!text) return;
  const blob = new Blob([text], { type: 'text/plain' });
  const file = new File([blob], 'pasted.fasta');
  await uploadFile(file);
  const si = document.getElementById('plSeqInfoPaste');
  if (si && document.getElementById('plSeqInfo').innerHTML) {
    si.innerHTML = document.getElementById('plSeqInfo').innerHTML;
    si.classList.remove('hidden');
  }
}

async function runPipeline() {
  if (!state.activeJob?.job_id) return;
  const steps = [];
  if (document.getElementById('stepAlign')?.checked) steps.push('align');
  if (document.getElementById('stepModel')?.checked) steps.push('modeltest');
  if (document.getElementById('stepTree')?.checked) steps.push('iqtree');
  if (document.getElementById('stepReport')?.checked) steps.push('report');

  const opts = {
    steps,
    schemes:   document.getElementById('cfgSchemes').value,
    topology:  document.getElementById('cfgTopology').value,
    template:  document.getElementById('cfgTemplate').value,
    bootstrap: document.getElementById('cfgBootstrap').value,
    threads:   document.getElementById('cfgThreads').value,
    asc_bias:  document.getElementById('cfgAsc').value,
  };

  document.getElementById('configCard').classList.add('hidden');
  document.getElementById('progressCard').classList.remove('hidden');
  renderPipelineProgress(steps, {});

  try {
    await apiPost('/api/pipeline/run', { job_id: state.activeJob.job_id, options: opts });
    startPolling(state.activeJob.job_id, steps);
  } catch(e) {
    logProgress(`Error: ${e.message}`);
  }
}

function startPolling(jobId, steps) {
  if (state.pollTimer) clearInterval(state.pollTimer);
  let pollCount = 0;

  state.pollTimer = setInterval(async () => {
    pollCount++;
    try {
      const job = await api(`/api/jobs/${jobId}`);
      renderPipelineProgress(steps, job);
      logProgress(`[${new Date().toLocaleTimeString()}] ${job.status} (${job.progress || 0}%)`);

      if (job.status === 'error') {
        clearInterval(state.pollTimer);
        await loadJobs();
        document.getElementById('progressCard').classList.add('hidden');
        const el = document.getElementById('plResults');
        el.classList.remove('hidden');
        const errMsg = job.error || 'Unknown error';
        const isToolMissing = errMsg.toLowerCase().includes('not found') || errMsg.includes('PATH');
        el.innerHTML = `
          <div style="background:rgba(248,113,113,.07);border:1px solid rgba(248,113,113,.3);
            border-radius:10px;padding:20px;margin-bottom:16px">
            <div style="color:var(--red);font-family:var(--display);font-size:15px;font-weight:700;margin-bottom:8px">
              Pipeline error
            </div>
            <div style="font-family:var(--mono);font-size:12px;color:var(--text-dim);margin-bottom:12px">${errMsg}</div>
            ${isToolMissing ? `
            <div style="color:var(--amber);font-size:12px;margin-top:8px">
              <strong>Tip:</strong> External tool not found in PATH.<br/>
              Uncheck Alignment and Tree inference in the config,
              run with Model selection only — the built-in Python engine
              requires no external tools.
            </div>` : ''}
          </div>`;
        return;
      }

      if (job.status === 'completed') {
        clearInterval(state.pollTimer);
        await loadJobs();
        const full = await api(`/api/jobs/${jobId}/full`);
        renderInlineResults(full);
      }

      if (pollCount >= 1800) {
        clearInterval(state.pollTimer);
        logProgress('Timeout — check job status in History.');
      }
    } catch(e) {}
  }, 2000);
}

function renderPipelineProgress(steps, job) {
  const status = job.status || 'running';
  const stepMap = { align:'aligning', modeltest:'model_selection', iqtree:'tree_inference', report:'generating_report' };
  const icons = { align:'⫴', modeltest:'⊞', iqtree:'⋱', report:'◈' };
  const labels = { align:'Align', modeltest:'Model', iqtree:'Tree', report:'Report' };

  let html = '';
  const enabled = steps;
  enabled.forEach((s, i) => {
    const curStatus = status === stepMap[s] ? 'running' : job.progress >= (i + 1) * (100 / enabled.length) ? 'done' : 'pending';
    html += `<div class="pp-step ${curStatus}">
      <div class="pp-icon">${icons[s]}</div>
      <div class="pp-label">${labels[s]}</div>
    </div>`;
    if (i < enabled.length - 1) {
      html += `<div class="pp-connector ${curStatus === 'done' ? 'done' : ''}"></div>`;
    }
  });
  document.getElementById('pipelineProgress').innerHTML = html;
}

function logProgress(msg) {
  const el = document.getElementById('progressLog');
  el.innerHTML += msg + '<br/>';
  el.scrollTop = el.scrollHeight;
}

// ── RESULTS RENDERING ──────────────────────────────────────
function renderInlineResults(job) {
  document.getElementById('progressCard').classList.add('hidden');
  const el = document.getElementById('plResults');
  el.classList.remove('hidden');
  el.innerHTML = buildResultsHTML(job);
  initResultsInteraction(job, el);
}

function showResultsModal(job) {
  document.getElementById('modalTitle').textContent = job.label || job.job_id.slice(0, 8);
  document.getElementById('modalBody').innerHTML = buildResultsHTML(job);
  initResultsInteraction(job, document.getElementById('modalBody'));
  document.getElementById('modalOverlay').classList.remove('hidden');
  document.getElementById('modalClose').onclick = () => document.getElementById('modalOverlay').classList.add('hidden');
}

function buildResultsHTML(job) {
  const mt = job.modeltest_result || {};
  const iq = job.iqtree_result || {};
  const si = job.seq_info || mt.dataset || {};
  const models = mt.models || [];
  const pi = mt.parameter_importances || {};
  const hlrt = mt.hlrt || {};
  const disclaimer = mt.disclaimer || '';

  if (!models.length && !mt.best_model_bic) {
    return `<div style="color:var(--text-dim);padding:20px">
      ${job.status === 'error' ? `<span style="color:var(--red)">Error: ${job.error}</span>` : 'Analysis running or no results yet.'}
    </div>`;
  }

  return `
    ${disclaimer ? `<div class="disclaimer-banner">⚠ ${disclaimer}</div>` : ''}

    <div class="best-models-grid">
      ${bmCard('aic',  'Best — AIC',  mt.best_model_aic)}
      ${bmCard('aicc', 'Best — AICc', mt.best_model_aicc)}
      ${bmCard('bic',  'Best — BIC ★',mt.best_model_bic)}
      ${hlrt.selected_model ? bmCard('hlrt','Best — hLRT',{name:hlrt.selected_model,lnL:''}) : ''}
    </div>

    <div class="dataset-strip">
      <span><strong>${si.n_sequences ?? '—'}</strong> sequences</span>
      <span><strong>${si.n_sites ?? '—'}</strong> sites</span>
      <span><strong>${si.datatype ?? '—'}</strong></span>
      <span>Models tested: <strong>${mt.n_models_tested ?? models.length}</strong></span>
      <span>Engine: <strong>${mt.engine ?? '—'}</strong></span>
    </div>

    <!-- Parameter importances -->
    <div class="section-sep">Parameter Importances (AIC weights)</div>
    <div class="pi-grid">
      ${piItem('+Γ Gamma', pi.gamma)}
      ${piItem('+I Invariant', pi.inv_sites)}
      ${piItem('+Γ+I Both', pi.gamma_inv)}
      ${piItem('+F Frequencies', pi.frequencies)}
    </div>

    <!-- hLRT -->
    ${hlrt.tests?.length ? `
      <div class="section-sep">Likelihood Ratio Tests (hLRT)</div>
      <div class="tbl-wrap">
        <table class="hlrt-tbl">
          <thead><tr>
            <th>H₀ (null)</th><th>H₁ (alt)</th><th>Description</th>
            <th>df</th><th>LR</th><th>p-value</th><th>Decision</th>
          </tr></thead>
          <tbody>
            ${hlrt.tests.map(t => `<tr>
              <td style="font-family:var(--mono)">${t.null}</td>
              <td style="font-family:var(--mono)">${t.alternative}</td>
              <td style="color:var(--text-dim)">${t.description}</td>
              <td style="font-family:var(--mono)">${t.df}</td>
              <td style="font-family:var(--mono)">${t.LR?.toFixed(3)}</td>
              <td style="font-family:var(--mono)">${t.p_value?.toFixed(5)}</td>
              <td class="${t.rejected ? 'rej-yes' : 'rej-no'}">${t.rejected ? 'Reject H₀' : 'Accept H₀'}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
      <p style="font-size:11px;color:var(--text-dim);margin:6px 0 14px">
        hLRT selected: <strong style="color:var(--green);font-family:var(--mono)">${hlrt.selected_model}</strong>
      </p>` : ''}

    <!-- Model table -->
    <div class="section-sep">
      <span>All Models</span>
      <div class="crit-switcher">
        <button class="cs-btn active" data-crit="AIC">AIC</button>
        <button class="cs-btn" data-crit="AICc">AICc</button>
        <button class="cs-btn" data-crit="BIC">BIC</button>
      </div>
    </div>
    <div class="tbl-wrap">
      <table class="model-tbl" id="modelTbl">
        <thead><tr>
          <th>#</th><th>Model</th>
          <th class="r">lnL</th><th class="r">K</th>
          <th class="r" id="critHdr">AIC</th>
          <th class="r">Δ</th><th>Weight</th><th>Props</th>
        </tr></thead>
        <tbody id="modelTbody"></tbody>
      </table>
    </div>

    <!-- Weight chart -->
    <div class="section-sep">Weight Distribution (top 15)</div>
    <div class="chart-box"><canvas id="weightChart"></canvas></div>

    <!-- IQ-TREE result -->
    ${iq.available ? `
      <div class="section-sep">IQ-TREE 2 — Tree Inference</div>
      <div class="dataset-strip">
        <span>Model: <strong>${iq.model_used}</strong></span>
        ${iq.lnL  ? `<span>lnL: <strong>${iq.lnL}</strong></span>` : ''}
        ${iq.bic  ? `<span>BIC: <strong>${iq.bic}</strong></span>` : ''}
      </div>
      ${iq.newick ? `<div class="methods-text" style="max-height:80px">${iq.newick}</div>` : ''}
    ` : ''}

    <!-- Export bar -->
    <div class="export-row">
      <span style="color:var(--text-dim);font-size:12px">Export:</span>
      <button class="btn-outline sm" onclick="window.open('/api/report/export/${job.job_id}/json')">JSON</button>
      <button class="btn-outline sm" onclick="window.open('/api/report/export/${job.job_id}/csv')">CSV</button>
      <button class="btn-outline sm" onclick="window.open('/api/report/export/${job.job_id}/txt')">TXT</button>
      <button class="btn-outline sm" id="btnGetReport">Full Report</button>
    </div>
    <div id="reportPanel" class="hidden"></div>
  `;
}

function bmCard(cls, label, m) {
  if (!m) return '';
  return `<div class="bm-card ${cls}">
    <div class="bm-crit">${label}</div>
    <div class="bm-name">${m.name || '—'}</div>
    <div class="bm-score">lnL ${fmt(m.lnL)} · K=${m.K ?? '—'}</div>
  </div>`;
}

function piItem(label, val) {
  const v = parseFloat(val) || 0;
  return `<div class="pi-item">
    <div class="pi-label">${label}</div>
    <div class="pi-bar-wrap"><div class="pi-bar" style="width:${Math.round(v*100)}%"></div></div>
    <div class="pi-val">${v.toFixed(4)}</div>
  </div>`;
}

function initResultsInteraction(job, container) {
  const models = (job.modeltest_result || {}).models || [];
  if (!models.length) return;

  // Criterion switcher
  container.querySelectorAll('.cs-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      container.querySelectorAll('.cs-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const crit = btn.dataset.crit;
      renderModelTable(models, crit, container);
      renderChart(models, crit, container);
    });
  });

  renderModelTable(models, 'AIC', container);
  renderChart(models, 'AIC', container);

  // Report button
  const rBtn = container.querySelector('#btnGetReport');
  if (rBtn) rBtn.addEventListener('click', () => loadReport(job, container));
}

function renderModelTable(models, crit, container) {
  const sorted = [...models].sort((a, b) => (a[crit] || 0) - (b[crit] || 0));
  const maxW = Math.max(...sorted.map(m => m[`weight_${crit}`] || 0), 0.001);
  const hdr = container.querySelector('#critHdr');
  if (hdr) hdr.textContent = crit;
  const tbody = container.querySelector('#modelTbody');
  if (!tbody) return;

  tbody.innerHTML = sorted.slice(0, 50).map((m, i) => {
    const w = m[`weight_${crit}`] || 0;
    const d = m[`delta_${crit}`] || 0;
    const bw = Math.round((w / maxW) * 80);
    const tags = [
      m.has_G && '<span class="wtag hi">+Γ</span>',
      m.has_I && '<span class="wtag hi">+I</span>',
      m.has_F && '<span class="wtag hi">+F</span>',
    ].filter(Boolean).join('') || '<span class="wtag">base</span>';
    return `<tr class="${i === 0 ? 'rank1' : ''}">
      <td class="num" style="color:var(--text-faint)">${i + 1}</td>
      <td><span class="mn">${m.name}</span></td>
      <td class="num">${fmt(m.lnL)}</td>
      <td class="num">${m.K}</td>
      <td class="num" style="color:${i === 0 ? 'var(--teal)' : 'inherit'}">${fmt(m[crit])}</td>
      <td class="num" style="color:var(--text-dim)">${fmt(d)}</td>
      <td>
        <div style="display:flex;align-items:center;gap:6px">
          <div style="width:${bw}px;height:3px;background:var(--teal);border-radius:2px;min-width:1px"></div>
          <span style="font-family:var(--mono);font-size:10px;color:var(--text-dim)">${(w*100).toFixed(2)}%</span>
        </div>
      </td>
      <td>${tags}</td>
    </tr>`;
  }).join('');
}

function renderChart(models, crit, container) {
  const canvas = container.querySelector('#weightChart');
  if (!canvas) return;
  const sorted = [...models].sort((a, b) => (a[crit] || 0) - (b[crit] || 0)).slice(0, 15);
  const labels = sorted.map(m => m.name);
  const weights = sorted.map(m => ((m[`weight_${crit}`] || 0) * 100).toFixed(3));

  if (state.chart) { try { state.chart.destroy(); } catch(e) {} }
  const ctx = canvas.getContext('2d');
  state.chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: `${crit} Weight (%)`,
        data: weights,
        backgroundColor: sorted.map((_, i) => i === 0 ? 'rgba(0,229,176,.85)' : 'rgba(0,229,176,.25)'),
        borderColor: 'rgba(0,229,176,.9)',
        borderWidth: 1,
        borderRadius: 3,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#607a97', font: { family: 'IBM Plex Mono', size: 9 } }, grid: { color: 'rgba(28,47,66,.8)' } },
        y: { ticks: { color: '#607a97', font: { family: 'IBM Plex Mono', size: 9 } }, grid: { color: 'rgba(28,47,66,.8)' } },
      },
    },
  });
}

async function loadReport(job, container) {
  const panel = container.querySelector('#reportPanel');
  if (!panel) return;
  panel.classList.remove('hidden');
  panel.innerHTML = '<p style="color:var(--text-dim);font-size:12px">Generating report…</p>';
  try {
    const data = await apiPost(`/api/report/generate/${job.job_id}`, {});
    const cmds = data.commands || {};
    panel.innerHTML = `
      <div class="section-sep" style="margin-top:20px">Methods Section (copy into manuscript)</div>
      <div class="methods-text">${data.methods || ''}</div>
      <div class="section-sep">Commands for Downstream Tools</div>
      <div class="commands-grid">
        ${Object.entries(cmds).map(([tool, cmd]) => `
          <div class="cmd-item">
            <div class="cmd-label">${tool}</div>
            <div class="cmd-text">${cmd}</div>
          </div>`).join('')}
      </div>
      ${data.pdf_available ? `
        <div class="export-row" style="margin-top:10px">
          <button class="btn-primary" onclick="window.open('/api/report/download/${job.job_id}/pdf')">⬇ Download PDF Report</button>
        </div>` : `<p class="disclaimer-banner">${data.pdf_message || ''}</p>`}
    `;
  } catch(e) {
    panel.innerHTML = `<p style="color:var(--red)">Report error: ${e.message}</p>`;
  }
}

// ── DATABASE VIEW ──────────────────────────────────────────
function initDatabaseView() {
  let activeDB = 'ncbi';

  document.querySelectorAll('.db-hero-card').forEach(card => {
    card.addEventListener('click', () => {
      document.querySelectorAll('.db-hero-card').forEach(c => c.classList.remove('active'));
      card.classList.add('active');
      activeDB = card.dataset.db;
      document.getElementById('dbSearchTitle').textContent = card.querySelector('.dbh-name').textContent;
      document.getElementById('boldSearchOpts').classList.toggle('hidden', activeDB !== 'bold');
    });
  });

  document.getElementById('dbBtnSearch')?.addEventListener('click', async () => {
    const query = document.getElementById('dbSearchQuery').value.trim();
    if (!query) return;
    const el = document.getElementById('dbSearchResults');
    el.classList.remove('hidden');
    el.innerHTML = '<p style="color:var(--text-dim);font-size:12px;padding:8px">Searching…</p>';

    try {
      let data;
      if (activeDB === 'bold') {
        data = await apiPost('/api/database/bold-search', {
          taxon: query,
          marker: document.getElementById('dbBoldMarker').value,
          geo: document.getElementById('dbBoldGeo').value,
          max_results: document.getElementById('dbSearchMax').value,
        });
      } else {
        data = await apiPost('/api/database/search', {
          database: activeDB, query,
          db_type: document.getElementById('dbSearchType').value,
          max_results: document.getElementById('dbSearchMax').value,
        });
      }
      const acc = new Set();
      renderSearchResults(data.results || [], el, 'dbFetchBar', 'dbFetchCount', acc);
      // Store accessions ref for db view
      window._dbAccessions = acc;
    } catch(e) {
      el.innerHTML = `<p style="color:var(--red);font-size:12px;padding:8px">Error: ${e.message}</p>`;
    }
  });

  document.getElementById('dbBtnFetch')?.addEventListener('click', async () => {
    const accessions = [...(window._dbAccessions || state.selectedAccessions)];
    if (!accessions.length) return;
    showSeqInfo('dbSeqInfo', { status: 'Fetching…' });
    try {
      const endpoint = activeDB === 'bold' ? '/api/database/bold-fetch' : '/api/database/fetch';
      const body = activeDB === 'bold'
        ? { process_ids: accessions, marker: document.getElementById('dbBoldMarker').value }
        : { accessions, database: activeDB, db_type: document.getElementById('dbSearchType').value };
      const data = await apiPost(endpoint, body);
      showSeqInfo('dbSeqInfo', data);
      await loadJobs();
    } catch(e) { showSeqInfo('dbSeqInfo', { error: e.message }); }
  });
}

// ── COMPARE VIEW ───────────────────────────────────────────
function initCompareView() {
  document.getElementById('btnCompare')?.addEventListener('click', runCompare);
}

function renderCompareJobList() {
  const el = document.getElementById('compareJobList');
  const completed = state.jobs.filter(j => j.status === 'completed' && j.best_model);
  el.innerHTML = completed.length ? completed.map(j => `
    <div class="cjl-item" data-jid="${j.job_id}">
      <span class="cjl-check"><input type="checkbox" data-jid="${j.job_id}"/></span>
      <span class="cjl-name">${j.label || j.job_id.slice(0,8)}</span>
      <span class="cjl-meta">${j.seq_info?.n_sequences ?? '?'} seq · BIC: ${j.best_model}</span>
    </div>`).join('') : '<p style="color:var(--text-dim);font-size:12px">No completed jobs yet.</p>';

  el.querySelectorAll('input[type=checkbox]').forEach(cb => {
    cb.addEventListener('change', () => {
      if (cb.checked) state.compareSelected.add(cb.dataset.jid);
      else state.compareSelected.delete(cb.dataset.jid);
    });
  });
}

async function runCompare() {
  if (state.compareSelected.size < 2) { alert('Select at least 2 completed jobs.'); return; }
  const el = document.getElementById('compareResults');
  el.classList.remove('hidden');
  el.innerHTML = '<p style="color:var(--text-dim);font-size:12px">Comparing…</p>';
  try {
    const data = await apiPost('/api/pipeline/compare', { job_ids: [...state.compareSelected] });
    renderCompare(data.comparison || [], el);
  } catch(e) {
    el.innerHTML = `<p style="color:var(--red)">Error: ${e.message}</p>`;
  }
}

function renderCompare(items, el) {
  el.innerHTML = `
    <div class="section-sep" style="margin-top:4px">Comparison — ${items.length} datasets</div>
    <div class="compare-grid">
      ${items.map(item => {
        const agree = item.criterion_agreement;
        const agreeCls = agree === 1 ? 'agree-full' : agree >= 0.66 ? 'agree-part' : 'agree-none';
        const agreeLabel = agree === 1 ? 'Full agreement' : agree >= 0.66 ? 'Partial agreement' : 'Disagreement';
        return `<div class="compare-card">
          <h3>${item.label || item.job_id.slice(0,8)}</h3>
          <div style="font-size:11px;color:var(--text-dim);line-height:2">
            <div>Sequences: <strong style="color:var(--text)">${item.seq_info?.n_sequences ?? '?'}</strong></div>
            <div>Sites: <strong style="color:var(--text)">${item.seq_info?.n_sites ?? '?'}</strong></div>
            <div>AIC:  <strong style="font-family:var(--mono);color:var(--teal)">${item.best_aic ?? '—'}</strong></div>
            <div>AICc: <strong style="font-family:var(--mono);color:var(--purple)">${item.best_aicc ?? '—'}</strong></div>
            <div>BIC:  <strong style="font-family:var(--mono);color:var(--amber)">${item.best_bic ?? '—'}</strong></div>
            <div>hLRT: <strong style="font-family:var(--mono);color:var(--green)">${item.best_hlrt ?? '—'}</strong></div>
          </div>
          <span class="agree-badge ${agreeCls}">${agreeLabel} (${Math.round(agree*100)}%)</span>
        </div>`;
      }).join('')}
    </div>`;
}

// ── REPORT VIEW ────────────────────────────────────────────
function initReportView() {
  document.getElementById('btnGenerateReport')?.addEventListener('click', async () => {
    const jid = state.reportJobId;
    if (!jid) { alert('Select a job first.'); return; }
    const full = await api(`/api/jobs/${jid}/full`);
    const el = document.getElementById('reportOutput');
    el.classList.remove('hidden');
    await loadReport(full, el);
    if (!el.querySelector('#reportPanel')) el.innerHTML += '<div id="reportPanel"></div>';
    loadReport(full, el);
  });
}

function renderReportJobList() {
  const el = document.getElementById('reportJobList');
  const completed = state.jobs.filter(j => j.status === 'completed');
  el.innerHTML = completed.length ? completed.map(j => `
    <div class="cjl-item" data-jid="${j.job_id}" onclick="selectReportJob('${j.job_id}', this)">
      <span class="jm-dot completed"></span>
      <span class="cjl-name">${j.label || j.job_id.slice(0,8)}</span>
      <span class="cjl-meta">${j.best_model ?? ''}</span>
    </div>`).join('') : '<p style="color:var(--text-dim);font-size:12px">No completed jobs yet.</p>';
}

function selectReportJob(jid, el) {
  document.querySelectorAll('#reportJobList .cjl-item').forEach(e => e.classList.remove('selected'));
  el.classList.add('selected');
  state.reportJobId = jid;
}

// ── SEARCH RESULTS RENDERER (shared) ──────────────────────
function renderSearchResults(results, container, fetchBarId, countId, accSet) {
  const acc = accSet || state.selectedAccessions;
  acc.clear();
  if (!results.length) { container.innerHTML = '<p style="color:var(--text-dim);font-size:12px;padding:8px">No results.</p>'; return; }
  container.innerHTML = `
    <table class="result-tbl">
      <thead><tr>
        <th></th><th>Accession</th><th>Title / Species</th><th>Organism</th><th>Length</th>
      </tr></thead>
      <tbody>
        ${results.map(r => `<tr>
          <td><input type="checkbox" data-acc="${r.accession || r.process_id}"/></td>
          <td><span class="acc-chip">${r.accession || r.process_id || '—'}</span></td>
          <td style="max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.title}</td>
          <td style="font-style:italic;font-size:11px;color:var(--text-dim)">${r.organism || '—'}</td>
          <td style="font-family:var(--mono)">${r.length ?? '—'}</td>
        </tr>`).join('')}
      </tbody>
    </table>`;
  container.querySelectorAll('input[type=checkbox]').forEach(cb => {
    cb.addEventListener('change', () => {
      if (cb.checked) acc.add(cb.dataset.acc);
      else acc.delete(cb.dataset.acc);
      const bar = document.getElementById(fetchBarId);
      const cnt = document.getElementById(countId);
      bar.classList.toggle('hidden', acc.size === 0);
      if (cnt) cnt.textContent = `${acc.size} selected`;
    });
  });
}

// ── UI HELPERS ─────────────────────────────────────────────
function showSeqInfo(elId, data) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.classList.remove('hidden');
  if (data.error) {
    el.style.borderLeftColor = 'var(--red)';
    el.innerHTML = `<div class="si-item"><div class="si-label">Error</div><div class="si-value" style="color:var(--red)">${data.error}</div></div>`;
    return;
  }
  el.style.borderLeftColor = '';
  const fields = [
    ['Sequences', data.n_sequences ?? (typeof data.sequences === 'number' ? data.sequences : Object.keys(data.sequences || {}).length || '—')],
    ['Sites',     data.n_sites    ?? data.sites],
    ['Format',    data.format],
    ['Data type', data.datatype],
    ['Source',    data.source ?? 'local'],
    data.gap_pct  != null ? ['Gaps',    data.gap_pct + '%']     : null,
    data.status             ? ['Status', data.status]             : null,
  ].filter(Boolean);
  el.innerHTML = fields.map(([l, v]) => `
    <div class="si-item">
      <div class="si-label">${l}</div>
      <div class="si-value">${v ?? '—'}</div>
    </div>`).join('');
}

function fmt(v) {
  if (v == null || v === '') return '—';
  return typeof v === 'number' ? v.toFixed(4) : v;
}

// ── API HELPERS ────────────────────────────────────────────
async function api(path) {
  const r = await fetch(`${API}${path}`);
  return r.json();
}

async function apiPost(path, body) {
  const r = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}
