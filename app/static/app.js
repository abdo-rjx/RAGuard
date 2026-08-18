/* RAGGuard frontend — login, permission-aware chat, admin (documents + audit). */
"use strict";

/* ---------- state ---------- */
// Token is now in an httpOnly cookie — we don't store it in localStorage
let user = null;          // { id, username, role, department, is_system_admin, is_security_admin }
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
  // Token is sent automatically via httpOnly cookie — no need to add Authorization header

  const res = await fetch(path, { ...options, headers, credentials: "include" });
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
  // Token is now stored in httpOnly cookie — no localStorage needed
  // We just need to fetch /auth/me to get user info
}

async function logout(showToast = true) {
  // Call the logout endpoint to clear the cookie
  try {
    await api("/auth/logout", { method: "POST" });
  } catch (_) {
    // Ignore errors — we'll clear local state anyway
  }
  user = null;
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
  const roleLabel =
    user.is_system_admin && user.is_security_admin ? " · system + security admin" :
    user.is_system_admin ? " · system admin" :
    user.is_security_admin ? " · security admin" : "";
  $("user-role").textContent = `${user.role} · ${user.department}` + roleLabel;
  $("user-avatar").textContent = user.username.slice(0, 2);
  // Feature A1 — separation of duties: system admins get the Admin tab
  // (documents + guard patterns); security admins get the Security tab
  // (audit logs + events + alerts + reports).
  $("admin-tab").hidden = !user.is_system_admin;
  $("security-tab").hidden = !user.is_security_admin;
  switchTab("chat");
  renderAccessCard();
  checkLLM();
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $("tab-chat").style.display = name === "chat" ? "contents" : "none";
  $("tab-admin").hidden = name !== "admin";
  $("tab-security").hidden = name !== "security";
  if (name === "admin") renderAdmin();
  if (name === "security") renderSecurityTab();
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
        <div class="feedback-row"></div>
      </div>`;
  } else {
    wrap.innerHTML = `<div class="bubble">${html}</div>`;
  }
  $("thread-inner").appendChild(wrap);
  scrollThread();
  return wrap;
}

/* Feature B3 — feedback: helpful / not helpful / report as security concern. */
function attachFeedback(wrap, query) {
  const row = wrap.querySelector(".feedback-row");
  if (!row) return;
  row.innerHTML = `
    <button class="fb" data-fb="thumbs_up" title="Helpful">👍</button>
    <button class="fb" data-fb="thumbs_down" title="Not helpful">👎</button>
    <button class="fb fb-alert" data-fb="security_concern" title="Report as security concern">🚩</button>`;
  row.querySelectorAll("[data-fb]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (btn.disabled) return;
      btn.disabled = true;
      try {
        await api("/chat/feedback", {
          method: "POST",
          body: JSON.stringify({ message: query, feedback: btn.dataset.fb }),
        });
        toast(btn.dataset.fb === "security_concern" ? "Reported as security concern" : "Thanks for your feedback", "ok");
      } catch (err) {
        toast(err.message, "error");
        btn.disabled = false;
      }
    });
  });
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
    const wrap = addMsg("assistant", renderAssistant(body));
    attachFeedback(wrap, message);
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
    body.innerHTML = `<tr class="empty-row"><td colspan="7">No documents match your filters.</td></tr>`;
    return;
  }

  body.innerHTML = rows.map((d) => `
    <tr>
      <td class="fname-cell" title="${escapeHtml(d.filename)}">${escapeHtml(d.filename)}</td>
      <td><span class="dept-badge">${escapeHtml(d.department)}</span></td>
      <td><span class="badge badge-${escapeHtml(d.classification)}">${escapeHtml(d.classification)}</span></td>
      <td>${d.chunk_count}</td>
      <td>${d.ingestion_status === "failed" ? `<span class="badge badge-DENY" title="${escapeHtml(d.ingestion_error || "")}">failed</span>` : `<span class="badge badge-ALLOW">ok</span>`}</td>
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

/* ---------- admin: security events ---------- */

let secPage = 1;
const SEC_PAGE_SIZE = 25;

function secQuery() {
  const p = new URLSearchParams();
  const user = $("sec-user").value.trim();
  const action = $("sec-action").value;
  if (user) p.set("user", user);
  if (action) p.set("action", action);
  p.set("page", secPage);
  p.set("page_size", SEC_PAGE_SIZE);
  return p;
}

async function renderSecurity() {
  const body = $("sec-body");
  body.innerHTML = `<tr class="empty-row"><td colspan="5">Loading…</td></tr>`;
  try {
    const qs = secQuery();
    const data = await api(`/security/events?${qs}`);
    const items = data.items || [];
    $("sec-page-info").textContent =
      data.total ? `Page ${secPage} · ${data.total} total` : "0 events";

    if (!items.length) {
      body.innerHTML = `<tr class="empty-row"><td colspan="5">No security events match your filters.</td></tr>`;
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
    $("sec-prev").disabled = secPage <= 1;
    $("sec-next").disabled = !data.total || secPage * SEC_PAGE_SIZE >= data.total;
  } catch (err) {
    body.innerHTML = `<tr class="empty-row"><td colspan="5">${escapeHtml(err.message)}</td></tr>`;
  }
}

/* ---------- admin: shared ---------- */

async function renderAdmin() {
  await Promise.all([loadDocs(), loadPatterns()]);
}

async function renderSecurityTab() {
  await Promise.all([renderSecurity(), renderAlerts(), renderReports()]);
}

/* ---------- system admin: guard patterns (A4) ---------- */

let patternsCache = [];

async function loadPatterns() {
  try {
    patternsCache = await api("/security/patterns");
  } catch (err) {
    patternsCache = [];
    toast(err.message, "error");
  }
  renderPatterns();
}

function renderPatterns() {
  const q = ($("pat-search").value || "").toLowerCase();
  const t = $("pat-type-filter").value;
  const rows = patternsCache.filter((p) =>
    (!q || p.pattern.toLowerCase().includes(q)) && (!t || p.type === t)
  );
  const body = $("pat-body");
  if (!rows.length) {
    body.innerHTML = `<tr class="empty-row"><td colspan="4">No patterns match your filters.</td></tr>`;
    return;
  }
  body.innerHTML = rows.map((p) => `
    <tr>
      <td class="mono" title="${escapeHtml(p.pattern)}">${escapeHtml(p.pattern)}</td>
      <td><span class="dept-badge">${escapeHtml(p.type)}</span></td>
      <td>${p.active ? `<span class="badge badge-ALLOW">active</span>` : `<span class="badge badge-DENY">inactive</span>`}</td>
      <td>
        <div class="row-actions">
          <button class="btn btn-secondary btn-sm" data-toggle="${p.id}">${p.active ? "Deactivate" : "Activate"}</button>
          <button class="btn btn-danger btn-sm" data-delpat="${p.id}" data-pat="${escapeHtml(p.pattern)}">Delete</button>
        </div>
      </td>
    </tr>`).join("");
  body.querySelectorAll("[data-toggle]").forEach((btn) => {
    btn.onclick = () => togglePattern(btn.dataset.toggle);
  });
  body.querySelectorAll("[data-delpat]").forEach((btn) => {
    btn.onclick = () => deletePattern(btn.dataset.delpat, btn.dataset.pat);
  });
}

async function togglePattern(id) {
  const p = patternsCache.find((x) => x.id === Number(id));
  if (!p) return;
  try {
    await api(`/security/patterns/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ pattern: p.pattern, type: p.type, active: !p.active }),
    });
    await loadPatterns();
  } catch (err) {
    toast(err.message, "error");
  }
}

async function deletePattern(id, pat) {
  if (!confirm(`Delete guard pattern "${pat}"?`)) return;
  try {
    await api(`/security/patterns/${id}`, { method: "DELETE" });
    await loadPatterns();
  } catch (err) {
    toast(err.message, "error");
  }
}

async function addPattern() {
  const type = prompt("Pattern type?", "injection");
  if (!type) return;
  const pattern = prompt("Regex pattern:");
  if (!pattern) return;
  try {
    await api("/security/patterns", { method: "POST", body: JSON.stringify({ pattern, type }) });
    await loadPatterns();
  } catch (err) {
    toast(err.message, "error");
  }
}

/* ---------- security admin: alerts (A5) + reports (A6) ---------- */

async function renderAlerts() {
  const body = $("alerts-body");
  try {
    const items = await api("/security/alerts");
    $("alerts-count").textContent = items.length;
    if (!items.length) {
      body.innerHTML = `<tr class="empty-row"><td colspan="4">No users currently flagged.</td></tr>`;
      return;
    }
    body.innerHTML = items.map((a) => `
      <tr>
        <td class="mono">${fmtTime(a.created_at)}</td>
        <td>${escapeHtml(a.username || "—")}${a.user_id ? ` <span class="did">#${a.user_id}</span>` : ""}</td>
        <td class="act">${escapeHtml(a.event_action)}</td>
        <td><span class="badge badge-DENY">${a.event_count}</span></td>
      </tr>`).join("");
  } catch (err) {
    body.innerHTML = `<tr class="empty-row"><td colspan="4">${escapeHtml(err.message)}</td></tr>`;
  }
}

async function renderReports() {
  const body = $("reports-body");
  try {
    const data = await api("/security/reports?page_size=50");
    const items = data.items || [];
    $("reports-count").textContent = data.total || 0;
    if (!items.length) {
      body.innerHTML = `<tr class="empty-row"><td colspan="4">No security reports submitted.</td></tr>`;
      return;
    }
    body.innerHTML = items.map((e) => `
      <tr>
        <td class="mono">${fmtTime(e.timestamp)}</td>
        <td>${escapeHtml(e.username || "—")}</td>
        <td class="mono" style="max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHtml(e.query_text || "")}">${escapeHtml((e.query_text || "").slice(0, 80))}</td>
        <td class="mono" style="max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHtml(e.reason || "")}">${escapeHtml((e.reason || "").slice(0, 80))}</td>
      </tr>`).join("");
  } catch (err) {
    body.innerHTML = `<tr class="empty-row"><td colspan="4">${escapeHtml(err.message)}</td></tr>`;
  }
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
  $("pat-search").addEventListener("input", renderPatterns);
  $("pat-type-filter").addEventListener("change", renderPatterns);
  $("pat-add-btn").addEventListener("click", addPattern);
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

  $("sec-apply").addEventListener("click", () => { secPage = 1; renderSecurity(); });
  $("sec-clear").addEventListener("click", () => {
    $("sec-user").value = "";
    $("sec-action").value = "";
    secPage = 1;
    renderSecurity();
  });
  $("sec-prev").addEventListener("click", () => { if (secPage > 1) { secPage--; renderSecurity(); } });
  $("sec-next").addEventListener("click", () => { secPage++; renderSecurity(); });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("upload-modal").hidden) closeUpload();
  });
}

/* ---------- boot ---------- */

const DEPTS = ["finance", "it", "hr", "security", "executive", "general"];

(async function boot() {
  initEvents();
  // Check if we have a valid session via the httpOnly cookie
  try {
    const me = await api("/auth/me");
    user = me;
    showApp();
    return;
  } catch (_) {
    /* no valid session → login view */
  }
  showLogin();
})();
