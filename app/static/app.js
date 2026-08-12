/* RAGGuard frontend — login, permission-aware chat, admin (documents + audit). */
"use strict";

/* ---------- state ---------- */
let token = localStorage.getItem("ragguard_token") || null;
let user = null;          // { id, username, role, department, is_admin }
let convCount = 0;

const $ = (id) => document.getElementById(id);

/* ---------- helpers ---------- */

function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

function fmtAgo(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return "";
  const s = Math.max(0, (Date.now() - d.getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 604800) return `${Math.floor(s / 86400)}d ago`;
  return d.toLocaleDateString();
}

function toast(msg, kind = "") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3800);
}

/* ---------- api ---------- */

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) {
    logout(false);
    throw new Error("Your session has expired. Please sign in again.");
  }
  if (res.status === 429) {
    throw new Error("Too many requests — slow down and try again in a moment.");
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const err = await res.json();
      if (err.detail) detail = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
    } catch (_) { /* keep default */ }
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

/* ---------- auth ---------- */

async function login(username, password) {
  const data = await api("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  token = data.access_token;
  localStorage.setItem("ragguard_token", token);
}

function logout(showToast = true) {
  token = null;
  user = null;
  localStorage.removeItem("ragguard_token");
  if (showToast) toast("Signed out", "ok");
  showLogin();
}

function showLogin() {
  $("app-view").hidden = true;
  $("login-view").hidden = false;
  $("login-username").focus();
}

function showApp() {
  $("login-view").hidden = true;
  $("app-view").hidden = false;
  $("user-name").textContent = user.username;
  $("user-role").textContent = `${user.role} · ${user.department}` + (user.is_admin ? " · admin" : "");
  $("user-avatar").textContent = user.username.slice(0, 2);
  $("admin-tab").hidden = !user.is_admin;
  switchTab("chat");
  renderAccessCard();
  checkLLM();
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $("tab-chat").style.display = name === "chat" ? "contents" : "none";
  $("tab-admin").hidden = name !== "admin";
  if (name === "admin") renderAdmin();
  if (name === "chat") $("chat-input").focus();
}

/* Access card — derived from the documents this user is actually allowed to see. */
async function renderAccessCard() {
  const list = $("access-list");
  list.innerHTML = "";
  try {
    const docs = await api("/documents");
    const pairs = {};
    for (const d of docs) {
      const key = `${d.department}`;
      const cur = pairs[key];
      pairs[key] = cur ? Math.max(cur, CLASS_ORDER.indexOf(d.classification)) : CLASS_ORDER.indexOf(d.classification);
    }
    const entries = Object.entries(pairs).sort((a, b) => a[0].localeCompare(b[0]));
    if (!entries.length) {
      list.innerHTML = `<div class="row">No document access</div>`;
      return;
    }
    for (const [dept, lvlIdx] of entries) {
      const lvl = CLASS_ORDER[Math.max(lvlIdx, 0)];
      const row = document.createElement("div");
      row.className = "row";
      row.innerHTML = `<span class="dept-badge">${escapeHtml(dept)}</span><span class="lvl">≤ ${escapeHtml(lvl)}</span>`;
      list.appendChild(row);
    }
  } catch (_) {
    list.innerHTML = `<div class="row">${escapeHtml(user.department)}</div>`;
  }
}

/* ---------- chat ---------- */

const CLASS_ORDER = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED", "TOP_SECRET"];

function addMsg(role, html) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  if (role === "assistant") {
    wrap.innerHTML = `
      <div class="avatar">
        <svg width="16" height="16" viewBox="0 0 32 32" aria-hidden="true">
          <path d="M16 2l11 4v9c0 7-4.5 12.5-11 15C9.5 27.5 5 22 5 15V6z" fill="#0b28a6"/>
          <path d="M11.5 16l3 3 6-6.5" stroke="#fff" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <div class="col">
        <div class="label">RAGGuard</div>
        <div class="bubble">${html}</div>
      </div>`;
  } else {
    wrap.innerHTML = `<div class="bubble">${html}</div>`;
  }
  $("thread-inner").appendChild(wrap);
  scrollThread();
  return wrap;
}

function scrollThread() {
  const t = $("thread");
  t.scrollTop = t.scrollHeight;
}

function sourcesHTML(sources) {
  if (!sources || !sources.length) return "";
  const items = sources.map((s) => `
    <li>
      <span class="dept-badge">${escapeHtml(s.department)}</span>
      <span class="badge badge-${escapeHtml(s.classification)}">${escapeHtml(s.classification)}</span>
      <span class="fname">${escapeHtml(s.filename)}</span>
      <span class="did">#${escapeHtml(s.document_id)}</span>
    </li>`).join("");
  return `
    <div class="sources">
      <details>
        <summary>Sources · ${sources.length}</summary>
        <ul>${items}</ul>
      </details>
    </div>`;
}

function renderAssistant(body) {
  const note = body.retrieval_note && body.retrieval_note !== "ok"
    ? `<div class="note">${escapeHtml(body.retrieval_note)}</div>` : "";
  return escapeHtml(body.answer) + sourcesHTML(body.sources) + note;
}

async function sendChat() {
  const input = $("chat-input");
  const message = input.value.trim();
  if (!message || $("chat-send").disabled) return;
  input.value = "";
  autoResize(input);
  $("chat-send").disabled = true;

  addMsg("user", escapeHtml(message));

  const typing = document.createElement("div");
  typing.className = "msg assistant";
  typing.innerHTML = `
    <div class="avatar">
      <svg width="16" height="16" viewBox="0 0 32 32" aria-hidden="true">
        <path d="M16 2l11 4v9c0 7-4.5 12.5-11 15C9.5 27.5 5 22 5 15V6z" fill="#0b28a6"/>
        <path d="M11.5 16l3 3 6-6.5" stroke="#fff" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    <div class="col">
      <div class="label">RAGGuard</div>
      <div class="bubble"><div class="typing-dots"><span></span><span></span><span></span></div></div>
    </div>`;
  $("thread-inner").appendChild(typing);
  scrollThread();

  try {
    const body = await api("/chat", { method: "POST", body: JSON.stringify({ message }) });
    typing.remove();
    addMsg("assistant", renderAssistant(body));
    convCount++;
    addRecentConv(message);
  } catch (err) {
    typing.remove();
    addMsg("assistant", `<div class="note" style="color:var(--red)">⚠ ${escapeHtml(err.message)}</div>`);
  } finally {
    $("chat-send").disabled = false;
    $("chat-input").focus();
  }
}

function addRecentConv(message) {
  const list = $("conv-list");
  const item = document.createElement("div");
  item.className = "conv-item";
  item.innerHTML = `<span class="t">${escapeHtml(message.slice(0, 60))}</span><span class="s">${fmtAgo(new Date().toISOString())}</span>`;
  item.onclick = () => item.classList.add("active");
  list.prepend(item);
  while (list.children.length > 8) list.lastChild.remove();
}

async function checkLLM() {
  const status = $("llm-status");
  const text = $("llm-status-text");
  try {
    await api("/health", {});
    text.textContent = "Connected";
    status.classList.remove("off");
  } catch (_) {
    text.textContent = "Model offline";
    status.classList.add("off");
  }
}

/* ---------- admin: documents ---------- */

let docsCache = [];

async function loadDocs() {
  try {
    docsCache = await api("/documents");
  } catch (err) {
    docsCache = [];
    toast(err.message, "error");
  }
  renderDocs();
  return docsCache;
}

function renderDocs() {
  const q = ($("doc-search").value || "").toLowerCase();
  const dept = $("doc-dept-filter").value;
  const cls = $("doc-class-filter").value;

  const rows = docsCache.filter((d) =>
    (!q || d.filename.toLowerCase().includes(q)) &&
    (!dept || d.department === dept) &&
    (!cls || d.classification === cls)
  );

  $("docs-count").textContent = docsCache.length;
  const body = $("docs-body");

  if (!rows.length) {
    body.innerHTML = `<tr class="empty-row"><td colspan="6">No documents match your filters.</td></tr>`;
    return;
  }

  body.innerHTML = rows.map((d) => `
    <tr>
      <td class="fname-cell" title="${escapeHtml(d.filename)}">${escapeHtml(d.filename)}</td>
      <td><span class="dept-badge">${escapeHtml(d.department)}</span></td>
      <td><span class="badge badge-${escapeHtml(d.classification)}">${escapeHtml(d.classification)}</span></td>
      <td>${d.chunk_count}</td>
      <td>${fmtTime(d.uploaded_at)}</td>
      <td>
        <div class="row-actions">
          <button class="btn btn-danger btn-sm" data-del="${d.id}" data-name="${escapeHtml(d.filename)}">Delete</button>
        </div>
      </td>
    </tr>`).join("");

  body.querySelectorAll("[data-del]").forEach((btn) => {
    btn.onclick = () => deleteDoc(btn.dataset.del, btn.dataset.name);
  });
}

async function deleteDoc(id, name) {
  if (!confirm(`Delete "${name}" and remove its chunks from the index?`)) return;
  try {
    await api(`/documents/${id}`, { method: "DELETE" });
    toast(`Deleted ${name}`, "ok");
    await loadDocs();
    renderAudit();
  } catch (err) {
    toast(err.message, "error");
  }
}

/* ---------- admin: upload ---------- */

let uploadFile = null;

function openUpload() {
  uploadFile = null;
  $("dz-label").innerHTML = "<b>Choose a file</b> or drag it here";
  $("doc-file").value = "";
  $("upload-modal").hidden = false;
  $("doc-dept").innerHTML = DEPTS.map((d) => `<option>${d}</option>`).join("");
  $("doc-class").innerHTML = CLASS_ORDER.map((c) => `<option>${c}</option>`).join("");
  $("doc-dept").value = user.department || "";
}

function closeUpload() {
  $("upload-modal").hidden = true;
}

async function submitUpload() {
  const file = uploadFile || $("doc-file").files[0];
  if (!file) { toast("Choose a file first", "error"); return; }
  const fd = new FormData();
  fd.append("file", file);
  fd.append("department", $("doc-dept").value);
  fd.append("classification", $("doc-class").value);

  const btn = $("upload-submit");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Uploading…`;
  try {
    const res = await api("/documents", { method: "POST", body: fd });
    toast(`Uploaded — ${res.chunks_created} chunk${res.chunks_created === 1 ? "" : "s"} indexed`, "ok");
    closeUpload();
    await loadDocs();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Upload";
  }
}

/* ---------- admin: audit ---------- */

let auditPage = 1;
const AUDIT_PAGE_SIZE = 25;

function auditQuery() {
  const p = new URLSearchParams();
  const user = $("audit-user").value.trim();
  const action = $("audit-action").value;
  const decision = $("audit-decision").value;
  if (user) p.set("user", user);
  if (action) p.set("action", action);
  if (decision) p.set("decision", decision);
  p.set("page", auditPage);
  p.set("page_size", AUDIT_PAGE_SIZE);
  return p;
}

async function renderAudit() {
  const body = $("audit-body");
  body.innerHTML = `<tr class="empty-row"><td colspan="5">Loading…</td></tr>`;
  try {
    const qs = auditQuery();
    const data = await api(`/audit/logs?${qs}`);
    const items = data.items || [];
    $("audit-page-info").textContent =
      data.total ? `Page ${auditPage} · ${data.total} total` : "0 events";

    if (!items.length) {
      body.innerHTML = `<tr class="empty-row"><td colspan="5">No audit events match your filters.</td></tr>`;
    } else {
      body.innerHTML = items.map((e) => `
        <tr>
          <td class="mono">${fmtTime(e.timestamp)}</td>
          <td>${escapeHtml(e.username || "—")}</td>
          <td class="act">${escapeHtml(e.action)}</td>
          <td>${e.decision ? `<span class="badge badge-${escapeHtml(e.decision)}">${escapeHtml(e.decision)}</span>` : "—"}</td>
          <td class="mono" style="max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-3);"
              title="${escapeHtml(e.reason || e.query_text || "")}">
            ${escapeHtml((e.reason || e.query_text || "").slice(0, 80))}
          </td>
        </tr>`).join("");
    }
    $("audit-prev").disabled = auditPage <= 1;
    $("audit-next").disabled = !data.total || auditPage * AUDIT_PAGE_SIZE >= data.total;
  } catch (err) {
    body.innerHTML = `<tr class="empty-row"><td colspan="5">${escapeHtml(err.message)}</td></tr>`;
  }
}

/* ---------- admin: shared ---------- */

async function renderAdmin() {
  await Promise.all([loadDocs(), renderAudit()]);
}

/* ---------- wire up ---------- */

function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 140) + "px";
}

function initEvents() {
  $("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("login-btn");
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Signing in…`;
    $("login-error").hidden = true;
    try {
      await login($("login-username").value.trim(), $("login-password").value);
      const me = await api("/auth/me");
      user = me;
      showApp();
    } catch (err) {
      $("login-error-text").textContent = err.message;
      $("login-error").hidden = false;
    } finally {
      btn.disabled = false;
      btn.textContent = "Sign in";
    }
  });

  $("logout-btn").addEventListener("click", () => logout());
  $("new-chat-btn").addEventListener("click", () => {
    $("thread-inner").innerHTML = "";
    convCount = 0;
    $("chat-input").focus();
  });

  document.querySelectorAll(".tab").forEach((b) =>
    b.addEventListener("click", () => switchTab(b.dataset.tab))
  );

  const input = $("chat-input");
  input.addEventListener("input", () => {
    autoResize(input);
    $("chat-send").disabled = !input.value.trim();
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });
  $("chat-send").addEventListener("click", sendChat);

  $("upload-btn").addEventListener("click", openUpload);
  $("upload-close").addEventListener("click", closeUpload);
  $("upload-cancel").addEventListener("click", closeUpload);
  $("upload-modal").addEventListener("click", (e) => {
    if (e.target === $("upload-modal")) closeUpload();
  });
  $("upload-form").addEventListener("submit", (e) => { e.preventDefault(); submitUpload(); });

  const dz = $("dropzone");
  dz.addEventListener("click", () => $("doc-file").click());
  $("doc-file").addEventListener("change", () => {
    const f = $("doc-file").files[0];
    if (f) {
      uploadFile = f;
      $("dz-label").innerHTML = `<span class="fname">${escapeHtml(f.name)}</span> · ${(f.size / 1024).toFixed(0)} KB`;
    }
  });
  ["dragover", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => {
    e.preventDefault();
    dz.classList.toggle("drag", ev === "dragover");
    if (ev === "drop" && e.dataTransfer.files[0]) {
      const f = e.dataTransfer.files[0];
      uploadFile = f;
      $("dz-label").innerHTML = `<span class="fname">${escapeHtml(f.name)}</span> · ${(f.size / 1024).toFixed(0)} KB`;
    }
  }));

  $("doc-search").addEventListener("input", renderDocs);
  $("doc-dept-filter").addEventListener("change", renderDocs);
  $("doc-class-filter").addEventListener("change", renderDocs);
  $("audit-apply").addEventListener("click", () => { auditPage = 1; renderAudit(); });
  $("audit-clear").addEventListener("click", () => {
    $("audit-user").value = "";
    $("audit-action").value = "";
    $("audit-decision").value = "";
    auditPage = 1;
    renderAudit();
  });
  $("audit-prev").addEventListener("click", () => { if (auditPage > 1) { auditPage--; renderAudit(); } });
  $("audit-next").addEventListener("click", () => { auditPage++; renderAudit(); });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("upload-modal").hidden) closeUpload();
  });
}

/* ---------- boot ---------- */

const DEPTS = ["finance", "it", "hr", "security", "executive", "general"];

(async function boot() {
  initEvents();
  if (token) {
    try {
      const me = await api("/auth/me");
      user = me;
      showApp();
      return;
    } catch (_) {
      /* token invalid → login view */
    }
  }
  showLogin();
})();
