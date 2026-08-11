"use strict";

/* ---------- state ---------- */
let token = null;
let user = null;

const $ = (id) => document.getElementById(id);

/* ---------- auth ---------- */
async function login(username, password) {
  const res = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Login failed");
  }
  const data = await res.json();
  token = data.access_token;
  user = { username, role: data.role, department: data.department, is_admin: data.is_admin };
  localStorage.setItem("ragguard_token", token);
}

function logout() {
  token = null;
  user = null;
  localStorage.removeItem("ragguard_token");
  showLogin();
}

/* ---------- api helpers ---------- */
function headers() {
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (res.status === 401) {
    logout();
    throw new Error("Session expired — please sign in again.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}

/* ---------- views ---------- */
function showLogin() {
  $("app-view").hidden = true;
  $("login-view").hidden = false;
}

function showApp() {
  $("login-view").hidden = true;
  $("app-view").hidden = false;
  $("user-chip").innerHTML = `<b>${escapeHtml(user.username)}</b> · ${escapeHtml(user.role)} · ${escapeHtml(user.department)}`;
  $("admin-tab").hidden = !user.is_admin;
  if (!user.is_admin && $("tab-admin").dataset.rendered) {
    switchTab("chat");
  }
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  $("tab-chat").hidden = name !== "chat";
  $("tab-admin").hidden = name !== "admin";
  if (name === "admin") renderAdmin();
}

/* ---------- chat ---------- */
function addMsg(role, text, meta = "") {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.innerHTML = escapeHtml(text) + (meta ? `<span class="meta">${meta}</span>` : "");
  $("chat-log").appendChild(div);
  $("chat-log").scrollTop = $("chat-log").scrollHeight;
  return div;
}

async function sendChat(message) {
  const typing = addMsg("assistant", "…", "");
  typing.classList.add("typing");
  typing.textContent = "RAGGuard is thinking…";
  try {
    const body = await api("/chat", { method: "POST", headers: headers(), body: JSON.stringify({ message }) });
    typing.remove();
    const sources = (body.sources || [])
      .map((s) => `<span class="tag">${escapeHtml(s.department)}</span> · ${escapeHtml(s.filename)}`)
      .join("<br>");
    addMsg("assistant", body.answer, sources ? "Sources: " + sources : "No documents were retrieved.");
  } catch (err) {
    typing.remove();
    addMsg("assistant", `⚠️ ${escapeHtml(err.message)}`);
  }
}

/* ---------- admin ---------- */
async function renderAdmin() {
  $("docs-table").querySelector("tbody").innerHTML = "";
  $("events-table").querySelector("tbody").innerHTML = "";
  $("upload-msg").textContent = "";

  const [docs, events] = await Promise.all([
    api("/documents", { headers: headers() }).catch(() => []),
    api("/security/events?page_size=50", { headers: headers() }).catch(() => ({ items: [] })),
  ]);

  const docRows = docs
    .map(
      (d) => `<tr>
        <td>${d.id}</td><td>${escapeHtml(d.filename)}</td><td>${escapeHtml(d.department)}</td>
        <td>${escapeHtml(d.classification)}</td><td>${d.chunk_count}</td>
        <td class="del"><button data-delete="${d.id}">Delete</button></td>
      </tr>`
    )
    .join("");
  $("docs-table").querySelector("tbody").innerHTML = docRows || `<tr><td colspan="6" class="muted">No documents.</td></tr>`;

  document.querySelectorAll("[data-delete]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm("Delete this document and its chunks?")) return;
      try {
        await api(`/documents/${btn.dataset.delete}`, { method: "DELETE", headers: headers() });
        renderAdmin();
      } catch (err) {
        alert(err.message);
      }
    });
  });

  const evRows = (events.items || [])
    .map(
      (e) => `<tr>
        <td>${escapeHtml(String(e.timestamp).slice(0, 19).replace("T", " "))}</td>
        <td class="badge-SUSPECTED">${escapeHtml(e.action)}</td>
        <td>${escapeHtml(e.username ?? "")}</td>
        <td class="badge-${e.decision}">${escapeHtml(e.decision ?? "")}</td>
        <td>${escapeHtml(e.reason ?? "")}</td>
      </tr>`
    )
    .join("");
  $("events-table").querySelector("tbody").innerHTML = evRows || `<tr><td colspan="5" class="muted">No security events.</td></tr>`;
}

async function uploadDoc() {
  const file = $("up-file").files[0];
  const department = $("up-department").value.trim();
  const classification = $("up-classification").value.trim().toUpperCase();
  if (!file || !department || !classification) {
    $("upload-msg").textContent = "Fill in file, department, and classification.";
    return;
  }
  const fd = new FormData();
  fd.append("file", file);
  fd.append("department", department);
  fd.append("classification", classification);
  try {
    const res = await fetch("/documents", { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Upload failed");
    }
    const data = await res.json();
    $("upload-msg").textContent = `Uploaded doc #${data.document_id} — ${data.chunks_created} chunk(s).`;
    $("up-file").value = "";
    renderAdmin();
  } catch (err) {
    $("upload-msg").textContent = `⚠️ ${err.message}`;
  }
}

/* ---------- wire-up ---------- */
$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("login-error").hidden = true;
  try {
    await login($("login-username").value, $("login-password").value);
    showApp();
  } catch (err) {
    $("login-error").textContent = err.message;
    $("login-error").hidden = false;
  }
});

$("logout-btn").addEventListener("click", logout);

document.querySelectorAll(".tab").forEach((t) =>
  t.addEventListener("click", () => switchTab(t.dataset.tab))
);

$("chat-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const msg = $("chat-input").value.trim();
  if (!msg) return;
  $("chat-input").value = "";
  addMsg("user", msg);
  sendChat(msg);
});

$("upload-form").addEventListener("submit", (e) => {
  e.preventDefault();
  uploadDoc();
});

/* restore session if a token is cached */
(function init() {
  const cached = localStorage.getItem("ragguard_token");
  if (cached) {
    token = cached;
    api("/auth/me", { headers: headers() })
      .then((me) => {
        user = me;
        showApp();
      })
      .catch(() => logout());
  }
})();
