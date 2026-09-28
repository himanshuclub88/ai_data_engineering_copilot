/*
  AI Data Engineering Copilot — static frontend
  Backend contract: the FastAPI endpoints exposed by server.py.

  IMPORTANT:
  Replace API_BASE with your PythonAnywhere URL before publishing to GitHub Pages.
*/

const API_BASE = "http://127.0.0.1:8000";
// Local development automatically uses FastAPI on port 8000.
const EFFECTIVE_API_BASE = ["localhost", "127.0.0.1"].includes(window.location.hostname)
  ? "http://127.0.0.1:8000"
  : API_BASE.replace(/\/$/, "");

const state = {
  jobs: [],
  summaries: new Map(),
  currentJob: null,
  currentPage: 1,
  pageSize: 25,
  totalPages: 1,
  totalRuns: 0,
  currentTab: "metadata",
  currentRun: null,
  currentRunLogs: null,
  currentRca: null,
  copilotAnswer: null,
  copilotBusy: false,
  homeBusy: false,
  jobBusy: false,
};

const app = document.getElementById("app");
const jobList = document.getElementById("job-list");
const topbarTitle = document.getElementById("topbar-title");
const connectionPill = document.getElementById("connection-pill");
const connectionText = document.getElementById("connection-text");
const modalRoot = document.getElementById("modal-root");
const toastRoot = document.getElementById("toast-root");

const themePicker = document.getElementById("theme-picker");
const themeMenu = document.getElementById("theme-menu");
const THEME_STORAGE_KEY = "ai-data-engineering-copilot-theme";
const THEMES = [
  "obsidian",
  "light",
  "slate",
  "cloud",
  "sand",
  "midnight",
  "emerald",
  "amethyst",
];

function updateThemeMeta(theme) {
  const meta = document.querySelector('meta[name="theme-color"]');
  const colors = {
    obsidian: "#070b16",
    light: "#f4f7fb",
    slate: "#e7ecf2",
    cloud: "#f8fafc",
    sand: "#f3efe8",
    midnight: "#050a16",
    emerald: "#06100e",
    amethyst: "#0f0a17",
  };
  if (meta) meta.setAttribute("content", colors[theme] || colors.obsidian);
}

function setTheme(theme, persist = true) {
  const chosen = THEMES.includes(theme) ? theme : "obsidian";
  document.documentElement.dataset.theme = chosen;
  updateThemeMeta(chosen);

  document.querySelectorAll(".theme-option").forEach((option) => {
    const active = option.dataset.theme === chosen;
    option.classList.toggle("active", active);
    option.setAttribute("aria-checked", String(active));
  });

  if (persist) {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, chosen);
    } catch (_) {
      // Continue without persistence when storage is unavailable.
    }
  }
}

function loadTheme() {
  let saved = "obsidian";
  try {
    saved = localStorage.getItem(THEME_STORAGE_KEY) || "obsidian";
  } catch (_) {
    // Use default theme.
  }
  setTheme(saved, false);
}

function toggleThemeMenu(force) {
  if (!themeMenu || !themePicker) return;
  const shouldOpen = typeof force === "boolean"
    ? force
    : !themeMenu.classList.contains("open");

  themeMenu.classList.toggle("open", shouldOpen);
  const button = themePicker.querySelector(".theme-button");
  if (button) button.setAttribute("aria-expanded", String(shouldOpen));
}


function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "—";
  return Number(value).toLocaleString("en-IN");
}

function formatPct(value) {
  if (value === null || value === undefined || value === "") return "—";
  return `${Number(value).toFixed(2)}%`;
}

function formatDuration(sec) {
  if (sec === null || sec === undefined || sec === "" || sec === "N/A") return "—";
  const s = Number(sec);
  if (!Number.isFinite(s)) return escapeHtml(sec);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = Math.floor(s % 60);
  return h ? `${h}h ${m}m ${ss}s` : `${m}m ${ss}s`;
}

function formatDate(value) {
  if (!value || value === "N/A") return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return escapeHtml(value);
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit"
  }).format(date);
}

function statusClass(status) {
  const normalized = String(status || "").toUpperCase();
  if (normalized === "FAILED") return "failed";
  if (normalized === "SUCCESS") return "success";
  return "other";
}

function showToast(message, type = "") {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  toastRoot.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

function setConnection(mode, text) {
  connectionPill.className = `connection-pill ${mode || ""}`;
  connectionText.textContent = text;
}

async function api(path, options = {}) {
  const response = await fetch(`${EFFECTIVE_API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  const raw = await response.text();
  let data = null;
  try { data = raw ? JSON.parse(raw) : null; } catch { data = raw; }

  if (!response.ok) {
    const message = data?.detail || data?.message || raw || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return data;
}

async function checkHealth() {
  try {
    await api("/health");
    setConnection("connected", "API Connected");
  } catch (error) {
    setConnection("failed", "API Unavailable");
  }
}

function renderSidebar() {
  document.querySelectorAll(".nav-home").forEach((el) => el.classList.toggle("active", !state.currentJob));

  jobList.innerHTML = state.jobs.map((job) => {
    const summary = state.summaries.get(job);
    const healthy = summary ? summary.failed <= summary.success : false;
    return `
      <button class="job-item ${job === state.currentJob ? "active" : ""}" data-action="job" data-job="${escapeHtml(job)}">
        <span class="nav-icon">◈</span>
        <span>${escapeHtml(job)}</span>
        <span class="job-status ${healthy ? "healthy" : ""}"></span>
      </button>
    `;
  }).join("");
}

function renderHomeSkeleton() {
  app.innerHTML = `
    <div class="loading-grid">
      <div class="skeleton large"></div>
      <div class="skeleton medium"></div>
      <div class="skeleton medium"></div>
    </div>
  `;
}

function renderJobSkeleton() {
  app.innerHTML = `
    <div class="loading-grid">
      <div class="skeleton small"></div>
      <div class="skeleton small"></div>
      <div class="skeleton large"></div>
      <div class="skeleton large"></div>
    </div>
  `;
}

async function loadJobs() {
  state.homeBusy = true;
  renderHomeSkeleton();
  try {
    const result = await api("/api/jobs");
    state.jobs = Array.isArray(result?.jobs) ? result.jobs : [];

    const summaryResults = await Promise.allSettled(
      state.jobs.map(async (job) => [job, await api(`/api/jobs/${encodeURIComponent(job)}/summary`)])
    );

    for (const item of summaryResults) {
      if (item.status === "fulfilled") {
        const [job, summary] = item.value;
        state.summaries.set(job, summary);
      }
    }

    renderSidebar();
    await renderHome();
  } catch (error) {
    app.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">!</div>
        <div class="empty-title">Could not load pipelines</div>
        <div class="empty-copy">${escapeHtml(error.message)}<br><br>Check API_BASE in app.js and confirm your FastAPI server is running.</div>
        <button class="btn primary" style="margin-top:16px" data-action="refresh">Retry</button>
      </div>
    `;
    showToast(error.message, "error");
  } finally {
    state.homeBusy = false;
  }
}

function calculateHealth() {
  const entries = [...state.summaries.values()];
  if (!entries.length) return 0;
  const total = entries.reduce((sum, s) => sum + Number(s.total || 0), 0);
  const success = entries.reduce((sum, s) => sum + Number(s.success || 0), 0);
  return total ? Math.round((success / total) * 100) : 0;
}

async function renderHome() {
  state.currentJob = null;
  topbarTitle.textContent = "Overview";
  renderSidebar();
  const health = calculateHealth();
  const totals = [...state.summaries.values()].reduce((acc, s) => {
    acc.total += Number(s.total || 0);
    acc.success += Number(s.success || 0);
    acc.failed += Number(s.failed || 0);
    acc.other += Number(s.other || 0);
    return acc;
  }, { total: 0, success: 0, failed: 0, other: 0 });

  app.innerHTML = `
    <div class="hero">
      <div class="hero-card">
        <div class="hero-kicker">OBSERVE · INVESTIGATE · EXPLAIN</div>
        <h1 class="hero-title">One console for your <span>data pipeline intelligence.</span></h1>
        <div class="hero-copy">Monitor jobs, drill into execution metadata, inspect logs, generate root-cause analysis, and ask the Copilot questions about pipeline history — all powered by your FastAPI backend.</div>
        <div class="hero-actions">
          ${state.jobs[0] ? `<button class="btn primary" data-action="job" data-job="${escapeHtml(state.jobs[0])}">Open a pipeline →</button>` : ""}
          <button class="btn" data-action="refresh">Refresh data</button>
        </div>
      </div>
      <div class="side-card">
        <div class="side-card-title">Portfolio health</div>
        <div class="health-score">
          <div>
            <div class="health-big">${health}%</div>
            <div class="health-label">success across all discovered runs</div>
          </div>
          <div style="font-size:28px;opacity:.75">✦</div>
        </div>
        <div class="progress"><span style="width:${health}%"></span></div>
        <div class="side-note">${formatNumber(totals.total)} total runs across ${state.jobs.length} pipelines · ${formatNumber(totals.failed)} failures recorded.</div>
      </div>
    </div>

    <div class="section-head">
      <div>
        <div class="section-title">Portfolio snapshot</div>
        <div class="section-subtitle">Live totals loaded from the FastAPI service.</div>
      </div>
      <div class="controls-row"><span class="side-note" style="margin:0">${new Date().toLocaleTimeString()}</span></div>
    </div>

    <div class="stats-grid">
      <div class="stat-card"><div class="stat-label">Pipelines</div><div class="stat-value">${formatNumber(state.jobs.length)}</div><div class="stat-caption">Available under DATA_ROOT</div></div>
      <div class="stat-card"><div class="stat-label">Runs</div><div class="stat-value">${formatNumber(totals.total)}</div><div class="stat-caption">Across all jobs</div></div>
      <div class="stat-card"><div class="stat-label">Success</div><div class="stat-value" style="color:var(--success)">${formatNumber(totals.success)}</div><div class="stat-caption">Completed successfully</div></div>
      <div class="stat-card"><div class="stat-label">Failed</div><div class="stat-value" style="color:var(--danger)">${formatNumber(totals.failed)}</div><div class="stat-caption">Require investigation</div></div>
    </div>

    <div class="section-head">
      <div>
        <div class="section-title">Pipelines</div>
        <div class="section-subtitle">Select a pipeline to inspect runs and open Copilot.</div>
      </div>
    </div>

    <div class="jobs-grid">
      ${state.jobs.map((job) => {
        const s = state.summaries.get(job) || {total:0,success:0,failed:0,other:0};
        const rate = Number(s.total) ? Math.round((Number(s.success) / Number(s.total)) * 100) : 0;
        return `
          <div class="job-card">
            <div class="job-top">
              <div>
                <div class="job-name">${escapeHtml(job)}</div>
                <div class="job-desc">${rate >= 80 ? "Stable delivery profile" : "Investigation recommended"}</div>
              </div>
              <button class="job-open" data-action="job" data-job="${escapeHtml(job)}">Open</button>
            </div>
            <div class="card-metrics">
              <div class="mini-metric"><div class="mini-label">Runs</div><div class="mini-value">${formatNumber(s.total)}</div></div>
              <div class="mini-metric"><div class="mini-label">Success</div><div class="mini-value good">${formatNumber(s.success)}</div></div>
              <div class="mini-metric"><div class="mini-label">Failed</div><div class="mini-value bad">${formatNumber(s.failed)}</div></div>
            </div>
            <div class="job-health"><span>${rate}% success rate</span><div class="progress"><span style="width:${rate}%"></span></div></div>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

async function openJob(jobName) {
  state.currentJob = jobName;
  state.currentPage = 1;
  state.currentRun = null;
  state.currentRunLogs = null;
  state.currentRca = null;
  state.copilotAnswer = null;
  topbarTitle.textContent = jobName;
  renderSidebar();
  renderJobSkeleton();
  await loadJobData();
}

async function loadJobData() {
  state.jobBusy = true;
  try {
    const [summary, runs] = await Promise.all([
      api(`/api/jobs/${encodeURIComponent(state.currentJob)}/summary`),
      api(`/api/jobs/${encodeURIComponent(state.currentJob)}/runs?page=${state.currentPage}&page_size=${state.pageSize}`)
    ]);
    state.summaries.set(state.currentJob, summary);
    state.runsResponse = runs;
    renderJobDashboard();
  } catch (error) {
    app.innerHTML = `
      <div class="alert error"><strong>Could not load ${escapeHtml(state.currentJob)}</strong><br>${escapeHtml(error.message)}</div>
      <button class="btn" style="margin-top:12px" data-action="refresh">Retry</button>
    `;
    showToast(error.message, "error");
  } finally {
    state.jobBusy = false;
  }
}

function renderJobDashboard() {
  const s = state.summaries.get(state.currentJob) || {total:0,success:0,failed:0,other:0};
  const runs = state.runsResponse?.runs || [];
  const successRate = Number(s.total) ? Math.round((Number(s.success) / Number(s.total)) * 100) : 0;

  app.innerHTML = `
    <div class="section-head" style="margin-top:0">
      <div>
        <div class="section-title" style="font-size:18px">${escapeHtml(state.currentJob)}</div>
        <div class="section-subtitle">Pipeline health, execution history and AI investigation.</div>
      </div>
      <div class="controls-row">
        <button class="btn small" data-action="home">← All pipelines</button>
        <button class="btn small" data-action="refresh">↻ Refresh</button>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card"><div class="stat-label">Total runs</div><div class="stat-value">${formatNumber(s.total)}</div><div class="stat-caption">Recorded executions</div></div>
      <div class="stat-card"><div class="stat-label">Success</div><div class="stat-value" style="color:var(--success)">${formatNumber(s.success)}</div><div class="stat-caption">${successRate}% success rate</div></div>
      <div class="stat-card"><div class="stat-label">Failed</div><div class="stat-value" style="color:var(--danger)">${formatNumber(s.failed)}</div><div class="stat-caption">Runs requiring attention</div></div>
      <div class="stat-card"><div class="stat-label">Other</div><div class="stat-value">${formatNumber(s.other)}</div><div class="stat-caption">Non-success / non-failed</div></div>
    </div>

    <div class="dashboard-grid" style="margin-top:16px">
      <section class="panel">
        <div class="panel-head">
          <div><div class="panel-title">Recent runs</div><div class="panel-subtitle">Showing ${runs.length ? `${state.runsResponse.showing.from}–${state.runsResponse.showing.to}` : 0} of ${formatNumber(state.runsResponse?.total || 0)} recent runs</div></div>
          <div class="panel-actions">
            <select class="select compact" id="page-size">
              ${[10,25,50,100].map(v => `<option value="${v}" ${v === state.pageSize ? "selected" : ""}>${v} / page</option>`).join("")}
            </select>
          </div>
        </div>
        <div class="table-wrap">
          ${runs.length ? `
          <table>
            <thead><tr><th>Run</th><th>Status</th><th>Start</th><th>Duration</th><th></th></tr></thead>
            <tbody>
              ${runs.map((r) => `
                <tr>
                  <td><button class="table-link run-id" data-action="run" data-run="${escapeHtml(r.iid)}">${escapeHtml(r.iid)}</button></td>
                  <td><span class="status-badge ${statusClass(r.status)}">${escapeHtml(r.status || "UNKNOWN")}</span></td>
                  <td>${formatDate(r.start_time)}</td>
                  <td>${formatDuration(r.duration_sec)}</td>
                  <td><button class="btn small" data-action="run" data-run="${escapeHtml(r.iid)}">Inspect</button></td>
                </tr>
              `).join("")}
            </tbody>
          </table>` : `<div class="empty-state"><div class="empty-icon">◌</div><div class="empty-title">No runs found</div><div class="empty-copy">This pipeline did not return any recent runs.</div></div>`}
        </div>
        <div class="pagination">
          <div>Page ${state.runsResponse?.page || 1} of ${state.runsResponse?.total_pages || 1}</div>
          <div class="page-buttons">
            <button class="btn small" data-action="page-prev" ${state.currentPage <= 1 ? "disabled" : ""}>←</button>
            <button class="btn small" data-action="page-next" ${state.currentPage >= (state.runsResponse?.total_pages || 1) ? "disabled" : ""}>→</button>
          </div>
        </div>
      </section>

      <section class="panel copilot-panel copilot-launch-panel">
        <div class="copilot-head">
          <div class="copilot-title-row">
            <div class="copilot-title"><span class="spark">✦</span> Data Engineering Copilot</div>
            <span class="status-dot" style="background:var(--success);box-shadow:0 0 0 4px var(--success-soft)"></span>
          </div>
          <div class="copilot-sub">Ask questions about ${escapeHtml(state.currentJob)}. Investigate runs, inspect generated SQL, review query results and retrieve RCA from the same FastAPI backend.</div>
        </div>
        <div class="copilot-launch-body">
          <div class="copilot-orb"><span>✦</span></div>
          <div class="copilot-launch-copy">
            <div class="copilot-launch-title">Your pipeline, explained.</div>
            <div class="copilot-launch-sub">Open the full-screen Copilot workspace for a focused investigation experience.</div>
          </div>
          <button class="btn primary copilot-open-btn" data-action="open-copilot">Open Copilot <span>↗</span></button>
          <div class="chips">
            <button class="chip" data-action="sample-question" data-question="Hi summary of last runs">Summary of last runs</button>
            <button class="chip" data-action="sample-question" data-question="Why did RUN_100 fail?">Latest failure</button>
            <button class="chip" data-action="sample-question" data-question="Give me RCA for RUN_100">RCA for RUN_100</button>
            <button class="chip" data-action="sample-question" data-question="Which runs had OUT_OF_MEMORY errors?">Memory failures</button>
          </div>
        </div>
      </section>
    </div>
  `;

  const pageSizeSelect = document.getElementById("page-size");
  pageSizeSelect?.addEventListener("change", async (event) => {
    state.pageSize = Number(event.target.value);
    state.currentPage = 1;
    await loadJobData();
  });

  document.getElementById("copilot-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runCopilot();
  });

  document.getElementById("copilot-question")?.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      document.getElementById("copilot-form")?.requestSubmit();
    }
  });
}

function openCopilotModal(prefill = "") {
  const existing = document.getElementById("copilot-modal");
  if (existing) {
    const input = existing.querySelector("#copilot-modal-question");
    if (prefill && input) input.value = prefill;
    input?.focus();
    return;
  }

  // One-shot analysis workspace:
  // the latest completed result remains when the modal is closed/reopened.
  state.copilotBusy = false;

  const modal = document.createElement("div");
  modal.id = "copilot-modal";
  modal.className = "copilot-modal-backdrop";
  modal.innerHTML = `
    <section class="copilot-modal" role="dialog" aria-modal="true" aria-label="Data Engineering Analysis">
      <header class="copilot-modal-head">
        <div class="copilot-modal-brand">
          <div class="copilot-modal-icon">✦</div>
          <div class="copilot-modal-title-wrap">
            <div class="copilot-modal-title">Data Engineering Analysis</div>
            <div class="copilot-modal-sub">${escapeHtml(state.currentJob || "Pipeline")} · analysis</div>
          </div>
        </div>

        <div class="copilot-modal-actions">
          <div class="analysis-state" id="analysis-state">READY</div>
          <span class="copilot-live"><span class="status-dot"></span> API Connected</span>
          <button class="icon-button" data-action="close-copilot" aria-label="Close analysis">✕</button>
        </div>
      </header>

      <main class="copilot-modal-main">
        <div class="copilot-modal-answer ${state.copilotAnswer ? "" : "empty"}" id="copilot-modal-answer">
          ${state.copilotAnswer ? renderCopilotAnswer(state.copilotAnswer) : `
            <div class="copilot-empty">
              <div class="copilot-empty-orb">✦</div>
              <div class="copilot-empty-title">Run an analysis</div>
              <div class="copilot-empty-copy">Question will be answered based on analysis of the pipeline using LLM.</div>
            </div>`}
        </div>
      </main>

      <footer class="copilot-modal-footer">
        <form class="copilot-modal-form" id="copilot-modal-form">
          <textarea id="copilot-modal-question" class="textarea copilot-modal-input" rows="2" aria-label="Analysis request" placeholder="Ask about the selected pipeline…">${escapeHtml(prefill || "")}</textarea>
          <div class="copilot-input-actions">
            <div class="kbd">Ctrl / ⌘ + Enter</div>
            <button class="btn primary copilot-send-btn" id="copilot-modal-submit" type="submit">Run Analysis →</button>
          </div>
        </form>
      </footer>
    </section>
  `;

  modalRoot.innerHTML = "";
  modalRoot.appendChild(modal);

  const form = document.getElementById("copilot-modal-form");
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runCopilot(true);
  });

  document.getElementById("copilot-modal-question")?.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      form?.requestSubmit();
    }
  });

  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeCopilotModal();
  });

  setTimeout(() => document.getElementById("copilot-modal-question")?.focus(), 0);
}

function closeCopilotModal() {
  const modal = document.getElementById("copilot-modal");
  if (modal) modal.remove();
}

function refreshCopilotModal() {
  const modal = document.getElementById("copilot-modal");
  if (!modal) return;
  const answer = modal.querySelector("#copilot-modal-answer");
  const button = modal.querySelector("#copilot-modal-submit");
  const input = modal.querySelector("#copilot-modal-question");
  const status = modal.querySelector("#analysis-state");
  if (answer) {
    answer.className = `copilot-modal-answer ${state.copilotAnswer ? "" : "empty"}`;
    answer.innerHTML = state.copilotAnswer
      ? renderCopilotAnswer(state.copilotAnswer)
      : `<div class="copilot-empty"><div class="copilot-empty-orb">✦</div><div class="copilot-empty-title">Run an analysis</div><div class="copilot-empty-copy">Question will be answered based on analysis of the pipeline using LLM.</div></div>`;
    answer.scrollTop = 0;
  }
  if (button) {
    button.disabled = state.copilotBusy;
    button.textContent = state.copilotBusy ? "Running Analysis…" : "Run Analysis →";
  }
  if (status) {
    status.textContent = state.copilotBusy ? "ANALYZING" : (state.copilotAnswer ? "COMPLETE" : "READY");
    status.className = `analysis-state ${state.copilotBusy ? "busy" : state.copilotAnswer ? "complete" : ""}`;
  }
  // The request box remains empty after an analysis. The latest result
  // stays visible until the user submits a new analysis.
  if (input && !state.copilotBusy && !state.copilotAnswer) {
    input.value = "";
  }
}

function renderCopilotAnswer(result) {
  if (!result) return "";
  const markdown = result.answer || "No answer returned.";
  let html;
  try {
    html = marked.parse(markdown, { breaks: true, gfm: true });
  } catch {
    html = `<p>${escapeHtml(markdown)}</p>`;
  }
  if (window.DOMPurify) html = DOMPurify.sanitize(html);

  const queries = Array.isArray(result.queries) ? result.queries : [];
  const rcas = Array.isArray(result.rcas) ? result.rcas : [];
  const plan = result.plan && typeof result.plan === "object" ? result.plan : null;

  return `
    <div class="answer-content">${html}</div>
    <div style="margin-top:14px;display:grid;gap:8px">
      ${plan ? `<details class="rca-card"><summary style="cursor:pointer;color:var(--text);font-weight:700;font-size:10px">Investigation plan</summary><pre class="code-log" style="margin-top:10px;max-height:260px">${escapeHtml(JSON.stringify(plan, null, 2))}</pre></details>` : ""}
      ${queries.map((q) => `
        <details class="rca-card">
          <summary style="cursor:pointer;color:var(--text);font-weight:700;font-size:10px">SQL ${escapeHtml(q.id ?? "")} · ${escapeHtml(q.purpose ?? "Query")}</summary>
          <pre class="code-log" style="margin-top:10px;max-height:220px">${escapeHtml(q.sql ?? q.SQL ?? "")}</pre>
          ${q.error ? `<div class="alert error" style="margin-top:9px">${escapeHtml(q.error)}</div>` : `<pre class="code-log" style="margin-top:9px;max-height:260px">${escapeHtml(JSON.stringify(q.result ?? [], null, 2))}</pre>`}
        </details>
      `).join("")}
      ${rcas.map((r) => `
        <details class="rca-card" open>
          <summary style="cursor:pointer;color:var(--text);font-weight:700;font-size:10px">RCA · ${escapeHtml(r.run_id ?? "")}</summary>
          <pre class="code-log" style="margin-top:10px;max-height:260px">${escapeHtml(JSON.stringify(r.rca ?? {}, null, 2))}</pre>
        </details>
      `).join("")}
    </div>
  `;
}

async function runCopilot(inModal = false) {
  const input = document.getElementById(inModal ? "copilot-modal-question" : "copilot-question");
  const question = input?.value?.trim();
  if (!question || !state.currentJob) return;

  state.copilotBusy = true;
  state.copilotAnswer = { question, answer: "Building investigation…" };

  // Clear the request box as soon as a new analysis starts.
  if (inModal && input) input.value = "";

  if (inModal) refreshCopilotModal();
  else renderJobDashboard();

  try {
    const result = await api(`/api/jobs/${encodeURIComponent(state.currentJob)}/copilot`, {
      method: "POST",
      body: JSON.stringify({ question }),
    });
    state.copilotAnswer = { ...result, question };
    showToast("Analysis complete", "success");
  } catch (error) {
    state.copilotAnswer = {
      question,
      answer: `### Copilot request failed\n\n${error.message}`,
    };
    showToast(error.message, "error");
  } finally {
    state.copilotBusy = false;
    if (inModal) {
      const modalInput = document.getElementById("copilot-modal-question");
      if (modalInput) modalInput.value = "";
      refreshCopilotModal();
      setTimeout(() => modalInput?.focus(), 0);
    } else {
      renderJobDashboard();
      setTimeout(() => document.getElementById("copilot-question")?.focus(), 0);
    }
  }
}

async function openRun(runId) {
  try {
    state.currentRun = await api(`/api/jobs/${encodeURIComponent(state.currentJob)}/runs/${encodeURIComponent(runId)}`);
    state.currentRunLogs = null;
    state.currentRca = null;
    state.currentTab = "metadata";
    renderRunDrawer();
  } catch (error) {
    showToast(error.message, "error");
  }
}

function renderRunDrawer() {
  const run = state.currentRun;
  if (!run) return;
  const status = run.status || "UNKNOWN";
  const executionData = run.data?.execution?.[0] || {};
  const modal = document.createElement("div");
  modal.className = "modal-backdrop";
  modal.innerHTML = `
    <div class="drawer" role="dialog" aria-modal="true" aria-label="Run details">
      <div class="drawer-head">
        <div>
          <div class="drawer-title">${escapeHtml(run.job)} / ${escapeHtml(run.run_id)}</div>
          <div class="drawer-sub">Detailed execution context</div>
          <div class="drawer-status"><span class="status-badge ${statusClass(status)}">${escapeHtml(status)}</span></div>
        </div>
        <div class="drawer-actions"><button class="btn small" data-action="generate-rca">Generate RCA</button><button class="icon-button" data-action="close-modal">✕</button></div>
      </div>
      <div class="drawer-tabs">
        ${["metadata","execution","rca"].map(tab => `<button class="tab ${state.currentTab === tab ? "active" : ""}" data-action="run-tab" data-tab="${tab}">${tab === "metadata" ? "Overview" : tab === "execution" ? "Execution Log" : "RCA"}</button>`).join("")}
      </div>
      <div class="drawer-body" id="drawer-body">${renderRunTabBody()}</div>
    </div>
  `;
  modalRoot.innerHTML = "";
  modalRoot.appendChild(modal);

  modal.addEventListener("click", async (event) => {
    if (event.target === modal) closeModal();
  });
}

function renderRunTabBody() {
  const run = state.currentRun;
  const execution = run.data?.execution?.[0] || {};

  if (state.currentTab === "metadata") {
    const tiles = [
      ["Run ID", run.run_id], ["Status", execution.status || run.status], ["Start", formatDate(execution.start_time || run.start_time)], ["Duration", formatDuration(execution.duration_sec ?? run.duration_sec)]
    ];
    const metadataJson = JSON.stringify(run.data || {}, null, 2);

    return `
      <div class="run-summary-grid">${tiles.map(([label, value]) => `<div class="summary-tile"><div class="summary-label">${escapeHtml(label)}</div><div class="summary-value">${escapeHtml(value)}</div></div>`).join("")}</div>
      <div class="metadata-hidden-row">
        <div>
          <div class="meta-title">Run metadata</div>
          <div class="metadata-hidden-note">Detailed DB metadata is available when needed.</div>
        </div>
        <button class="subtle-action" data-action="view-metadata-json">View JSON</button>
      </div>
    `;
  }

  if (state.currentTab === "execution" || state.currentTab === "error") {
    if (!state.currentRunLogs) {
      return `<div class="empty-state"><div class="empty-icon">…</div><div class="empty-title">Loading logs</div><div class="empty-copy">Reading execution and error logs from the backend.</div></div>`;
    }
    const text = state.currentTab === "execution" ? state.currentRunLogs.execution_log : state.currentRunLogs.error_log;
    return text ? `<div class="code-log">${escapeHtml(text)}</div>` : `<div class="alert">${state.currentTab === "execution" ? "execution.log" : "error.log"} not found.</div>`;
  }

  if (state.currentTab === "rca") {
    if (!state.currentRca) {
      return `
        <div class="empty-state">
          <div class="empty-icon">✦</div>
          <div class="empty-title">No RCA loaded</div>
          <div class="empty-copy">Generate root-cause analysis for this run. Cached RCA data from your backend can also be returned by this endpoint.</div>
          <button class="btn primary" style="margin-top:15px" data-action="generate-rca">Generate RCA</button>
        </div>
      `;
    }

    const rca = state.currentRca.rca ?? state.currentRca;
    const errorLog = state.currentRunLogs?.error_log;
    return `
      <div class="rca-grid">
        <div class="alert success">RCA loaded for ${escapeHtml(run.run_id)}.</div>
        ${[["Error", rca.error], ["Root Cause", rca.root_cause], ["Evidence", rca.evidence], ["Fix", rca.fix]].map(([label, value]) => `<div class="rca-card"><div class="rca-label">${label}</div><div class="rca-value">${escapeHtml(value ?? "—")}</div></div>`).join("")}
        <div class="rca-log-section">
          <div class="meta-title">Error log</div>
          ${errorLog ? `<div class="code-log rca-error-log">${escapeHtml(errorLog)}</div>` : `<div class="alert">error.log not found.</div>`}
        </div>
      </div>
    `;
  }
  return "";
}

async function ensureLogsLoaded() {
  if (state.currentRunLogs) return;
  const result = await api(`/api/jobs/${encodeURIComponent(state.currentJob)}/runs/${encodeURIComponent(state.currentRun.run_id)}/logs`);
  state.currentRunLogs = result;
}

async function generateRca() {
  if (!state.currentRun) return;
  const button = document.querySelector('[data-action="generate-rca"]');
  if (button) { button.disabled = true; button.textContent = "Analyzing…"; }
  try {
    state.currentRca = await api(`/api/jobs/${encodeURIComponent(state.currentJob)}/runs/${encodeURIComponent(state.currentRun.run_id)}/rca`, { method: "POST" });
    try {
      await ensureLogsLoaded();
    } catch {
      // RCA remains usable even if the error log cannot be loaded.
    }
    state.currentTab = "rca";
    renderRunDrawer();
    showToast("RCA generated", "success");
  } catch (error) {
    showToast(error.message, "error");
  }
}

function openMetadataJsonModal() {
  if (!state.currentRun) return;
  const existing = document.getElementById("metadata-json-modal");
  if (existing) return;

  const metadata = JSON.stringify(state.currentRun.data || {}, null, 2);
  const modal = document.createElement("div");
  modal.id = "metadata-json-modal";
  modal.className = "metadata-json-backdrop";
  modal.innerHTML = `
    <section class="metadata-json-modal" role="dialog" aria-modal="true" aria-label="Run metadata JSON">
      <header class="metadata-json-head">
        <div>
          <div class="drawer-title">Run Metadata</div>
          <div class="drawer-sub">${escapeHtml(state.currentRun.job)} / ${escapeHtml(state.currentRun.run_id)}</div>
        </div>
        <button class="icon-button" data-action="close-metadata-json" aria-label="Close metadata JSON">✕</button>
      </header>
      <div class="metadata-json-body"><pre class="code-log metadata-json-code">${escapeHtml(metadata)}</pre></div>
    </section>
  `;
  modalRoot.appendChild(modal);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) modal.remove();
  });
}

function closeModal() {
  modalRoot.innerHTML = "";
  state.currentRun = null;
  state.currentRunLogs = null;
  state.currentRca = null;
}

async function handleRunTab(tab) {
  state.currentTab = tab;
  renderRunDrawer();
  if ((tab === "execution" || tab === "error") && !state.currentRunLogs) {
    try {
      await ensureLogsLoaded();
      renderRunDrawer();
    } catch (error) {
      showToast(error.message, "error");
    }
  }
}

document.addEventListener("click", async (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.dataset.action;

  if (action === "home") {
    state.currentJob = null;
    closeModal();
    await renderHome();
    return;
  }

  if (action === "job") {
    await openJob(target.dataset.job);
    document.getElementById("sidebar")?.classList.remove("open");
    return;
  }

  if (action === "toggle-theme-menu") {
    toggleThemeMenu();
    return;
  }

  if (action === "select-theme") {
    setTheme(target.dataset.theme);
    toggleThemeMenu(false);
    return;
  }

  if (action === "refresh") {
    if (state.currentJob) await loadJobData();
    else await loadJobs();
    await checkHealth();
    return;
  }

  if (action === "run") {
    await openRun(target.dataset.run);
    return;
  }

  if (action === "page-prev") {
    if (state.currentPage > 1) {
      state.currentPage -= 1;
      await loadJobData();
    }
    return;
  }

  if (action === "page-next") {
    const totalPages = state.runsResponse?.total_pages || 1;
    if (state.currentPage < totalPages) {
      state.currentPage += 1;
      await loadJobData();
    }
    return;
  }

  if (action === "close-modal") {
    closeModal();
    return;
  }

  if (action === "view-metadata-json") {
    openMetadataJsonModal();
    return;
  }

  if (action === "close-metadata-json") {
    document.getElementById("metadata-json-modal")?.remove();
    return;
  }

  if (action === "open-copilot") {
    openCopilotModal();
    return;
  }

  if (action === "close-copilot") {
    closeCopilotModal();
    return;
  }

  if (action === "run-tab") {
    await handleRunTab(target.dataset.tab);
    return;
  }

  if (action === "generate-rca") {
    await generateRca();
    return;
  }

  if (action === "sample-question") {
    openCopilotModal(target.dataset.question || "");
    return;
  }

  if (action === "modal-sample-question") {
    const q = document.getElementById("copilot-modal-question");
    if (q) {
      q.value = target.dataset.question || "";
      q.focus();
    }
    return;
  }

  if (action === "toggle-sidebar") {
    document.getElementById("sidebar")?.classList.toggle("open");
  }
});

document.addEventListener("click", (event) => {
  if (themePicker && !themePicker.contains(event.target)) {
    toggleThemeMenu(false);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeModal();
    toggleThemeMenu(false);
  }
});

loadTheme();

(async function bootstrap() {
  setConnection("", "Checking API");
  await checkHealth();
  await loadJobs();
})();
