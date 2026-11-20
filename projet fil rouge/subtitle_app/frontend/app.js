"use strict";

const API = "/api/v1";
const POLL_MS = 2000;

const OUTPUTS = {
  video_embedded: { label: "Vidéo sous-titrée", desc: "Sous-titres incrustés dans l'image", video: true },
  video_metadata: { label: "Vidéo + piste", desc: "Sous-titres activables dans le lecteur", video: true },
  subtitles: { label: "Sous-titres seuls", desc: "Fichier .srt avec horodatage", video: false },
  text: { label: "Texte seul", desc: "Transcription sans horodatage", video: false },
};
const STATUS = { pending: "En attente", processing: "En cours", done: "Terminé", failed: "Échoué" };

const state = { token: null, user: null, jobs: [], pollTimer: null, viewerJob: null, viewerUrl: null };
const $ = (id) => document.getElementById(id);

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}
function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso + "Z").toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}
function fmtSeconds(s) {
  if (s == null) return "—";
  if (s < 60) return `${s.toFixed(1)} s`;
  const m = Math.floor(s / 60);
  return `${m} min ${String(Math.round(s % 60)).padStart(2, "0")}`;
}
function statusChip(status) {
  return `<span class="status ${status}">${STATUS[status]}</span>`;
}
function show(el, message) {
  el.textContent = message;
  el.hidden = !message;
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(API + path, { ...options, headers });
  if (response.status === 401 && state.token) {
    logoutLocal();
    throw new Error("Session expirée, reconnectez-vous.");
  }
  if (!response.ok) {
    let detail = `Erreur ${response.status}`;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : "Données invalides";
    } catch {}
    throw new Error(detail);
  }
  return response;
}

function saveToken(token) {
  try { sessionStorage.setItem("token", token ?? ""); } catch {}
}
function loadToken() {
  try { return sessionStorage.getItem("token") || null; } catch { return null; }
}

async function startSession() {
  state.user = await (await api("/auth/me")).json();
  $("who-name").textContent = state.user.username;
  $("who-role").textContent = state.user.role === "admin" ? "Administrateur" : "Utilisateur";
  $("admin-tab").hidden = state.user.role !== "admin";
  $("login-view").hidden = true;
  $("app-view").hidden = false;
  selectTab("jobs");
  await refreshJobs();
}

function logoutLocal() {
  state.token = null;
  state.user = null;
  saveToken(null);
  clearTimeout(state.pollTimer);
  closeViewer();
  $("app-view").hidden = true;
  $("login-view").hidden = false;
}

let signUpMode = false;

$("switch-mode").addEventListener("click", () => {
  signUpMode = !signUpMode;
  show($("login-error"), "");
  $("login-submit").textContent = signUpMode ? "Créer mon compte" : "Se connecter";
  $("switch-text").textContent = signUpMode ? "Déjà un compte ?" : "Pas encore de compte ?";
  $("switch-mode").textContent = signUpMode ? "Se connecter" : "Créer un compte";
  $("signup-rules").hidden = !signUpMode;
  $("login-password").autocomplete = signUpMode ? "new-password" : "current-password";
  const username = $("login-username");
  const password = $("login-password");
  if (signUpMode) {
    username.minLength = 3;
    username.maxLength = 50;
    username.pattern = "[A-Za-z0-9_.\\-]+";
    username.title = "Lettres sans accent, chiffres, _ . -";
    password.minLength = 6;
  } else {
    ["minlength", "maxlength", "pattern", "title"].forEach((attr) => username.removeAttribute(attr));
    password.removeAttribute("minlength");
  }
});

$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  show($("login-error"), "");
  const username = $("login-username").value;
  const password = $("login-password").value;
  try {
    const response = signUpMode
      ? await api("/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        })
      : await api("/auth/login", { method: "POST", body: new URLSearchParams({ username, password }) });
    state.token = (await response.json()).access_token;
    saveToken(state.token);
    $("login-password").value = "";
    await startSession();
  } catch (error) {
    show($("login-error"), error.message);
  }
});

$("logout-btn").addEventListener("click", async () => {
  try { await api("/auth/logout", { method: "POST" }); } catch {}
  logoutLocal();
});

function selectTab(name) {
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === name));
  $("jobs-panel").hidden = name !== "jobs";
  $("admin-panel").hidden = name !== "admin";
  if (name === "admin") refreshAdmin();
}
$("tabs").addEventListener("click", (event) => {
  const tab = event.target.closest(".tab");
  if (tab) selectTab(tab.dataset.tab);
});

let selectedFile = null;

function renderOutputs() {
  $("outputs").insertAdjacentHTML("beforeend", Object.entries(OUTPUTS).map(([value, o]) => `
    <label class="option">
      <input type="radio" name="output_type" value="${value}" id="out-${value}">
      <strong>${o.label}</strong>
      <span>${o.desc}</span>
    </label>`).join(""));
}

function fileKind(file) {
  const name = file.name.toLowerCase();
  if (name.endsWith(".mp4")) return "video";
  if (name.endsWith(".wav")) return "audio";
  return null;
}

function setFile(file) {
  show($("upload-error"), "");
  const kind = file ? fileKind(file) : null;
  if (file && !kind) {
    show($("upload-error"), "Format non pris en charge : choisissez une vidéo .mp4 ou un audio .wav.");
    file = null;
  }
  selectedFile = file;
  $("drop-zone").classList.toggle("filled", Boolean(file));
  $("drop-title").textContent = file ? file.name : "Déposez une vidéo .mp4 ou un audio .wav";
  $("drop-sub").textContent = file
    ? `${kind === "video" ? "Vidéo" : "Audio"} · ${(file.size / 1024 / 1024).toFixed(1)} Mo · cliquez pour changer`
    : "ou cliquez pour choisir un fichier";

  const isAudio = kind === "audio";
  for (const [value, o] of Object.entries(OUTPUTS)) {
    const input = $(`out-${value}`);
    input.disabled = isAudio && o.video;
    if (input.disabled && input.checked) input.checked = false;
  }
  $("audio-hint").hidden = !isAudio;
  updateSubmit();
}

function chosenOutput() {
  return document.querySelector('input[name="output_type"]:checked')?.value ?? null;
}
function updateSubmit() {
  $("upload-btn").disabled = !(selectedFile && chosenOutput());
}

$("file-input").addEventListener("change", (e) => setFile(e.target.files[0] ?? null));
$("outputs").addEventListener("change", updateSubmit);
const drop = $("drop-zone");
drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", (e) => {
  e.preventDefault();
  drop.classList.remove("over");
  setFile(e.dataTransfer.files[0] ?? null);
});

$("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  show($("upload-error"), "");
  const form = new FormData();
  form.append("file", selectedFile);
  form.append("output_type", chosenOutput());
  const button = $("upload-btn");
  button.disabled = true;
  button.textContent = "Envoi en cours…";
  try {
    await api("/jobs", { method: "POST", body: form });
    $("file-input").value = "";
    setFile(null);
    await refreshJobs();
  } catch (error) {
    show($("upload-error"), error.message);
  } finally {
    button.textContent = "Lancer le traitement";
    updateSubmit();
  }
});

function jobActions(job) {
  if (job.status !== "done") return "";
  if (job.files_purged) return `<span class="muted small">Fichiers supprimés</span>`;
  return `
    <button type="button" class="btn small" data-action="view" data-id="${job.id}">Voir</button>
    <button type="button" class="btn small" data-action="download" data-id="${job.id}">Télécharger</button>
    <button type="button" class="btn small ghost" data-action="purge" data-id="${job.id}">Supprimer</button>`;
}

function renderJobs() {
  $("jobs-empty").hidden = state.jobs.length > 0;
  $("jobs-body").innerHTML = state.jobs.map((job) => `
    <tr>
      <td class="file">${esc(job.original_filename)}</td>
      <td>${OUTPUTS[job.output_type].label}</td>
      <td>${statusChip(job.status)}${job.error_message ? `<span class="err-line">${esc(job.error_message)}</span>` : ""}</td>
      <td>${fmtDate(job.created_at)}</td>
      <td class="num">${fmtSeconds(job.media_duration_s)}</td>
      <td class="num">${fmtSeconds(job.processing_time_s)}</td>
      <td class="row-actions">${jobActions(job)}</td>
    </tr>`).join("");
}

async function refreshJobs() {
  clearTimeout(state.pollTimer);
  if (!state.token) return;
  try {
    state.jobs = await (await api("/jobs")).json();
    renderJobs();
  } catch {}
  if (state.jobs.some((job) => job.status === "pending" || job.status === "processing")) {
    state.pollTimer = setTimeout(refreshJobs, POLL_MS);
  }
}

$("jobs-body").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const job = state.jobs.find((j) => j.id === button.dataset.id);
  if (button.dataset.action === "view") openViewer(job);
  if (button.dataset.action === "download") downloadResult(job);
  if (button.dataset.action === "purge") {
    if (button.dataset.confirm !== "1") {
      button.dataset.confirm = "1";
      button.textContent = "Confirmer ?";
      return;
    }
    await api(`/jobs/${job.id}/files`, { method: "DELETE" });
    if (state.viewerJob?.id === job.id) closeViewer();
    await refreshJobs();
  }
});

async function fetchResult(job) {
  const response = await api(`/jobs/${job.id}/result`);
  const disposition = response.headers.get("content-disposition") || "";
  const match = disposition.match(/filename\*=utf-8''([^;]+)|filename="?([^";]+)"?/i);
  const filename = match ? decodeURIComponent(match[1] || match[2]) : "resultat";
  return { blob: await response.blob(), filename };
}

async function downloadResult(job) {
  const { blob, filename } = await fetchResult(job);
  const url = URL.createObjectURL(blob);
  const link = Object.assign(document.createElement("a"), { href: url, download: filename });
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function openViewer(job) {
  closeViewer();
  state.viewerJob = job;
  $("viewer").hidden = false;
  $("viewer-title").textContent = `${job.original_filename} · ${OUTPUTS[job.output_type].label}`;
  $("viewer-body").innerHTML = `<p class="muted">Chargement…</p>`;
  try {
    if (OUTPUTS[job.output_type].video) {
      const { blob } = await fetchResult(job);
      state.viewerUrl = URL.createObjectURL(blob);
      $("viewer-body").innerHTML = `<video controls src="${state.viewerUrl}"></video>`;
    } else {
      const { blob } = await fetchResult(job);
      $("viewer-body").innerHTML = `<pre>${esc(await blob.text())}</pre>`;
    }
    $("viewer").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    $("viewer-body").innerHTML = `<p class="error">${esc(error.message)}</p>`;
  }
}

function closeViewer() {
  if (state.viewerUrl) URL.revokeObjectURL(state.viewerUrl);
  state.viewerUrl = null;
  state.viewerJob = null;
  $("viewer").hidden = true;
  $("viewer-body").innerHTML = "";
}
$("viewer-close").addEventListener("click", closeViewer);
$("viewer-download").addEventListener("click", () => state.viewerJob && downloadResult(state.viewerJob));

function tile(label, value, sub = "", tone = "") {
  return `<div class="tile ${tone}"><span class="label">${label}</span><span class="value">${value}</span><span class="sub">${sub}</span></div>`;
}

async function refreshAdmin() {
  const [stats, history, users] = await Promise.all([
    api("/admin/stats").then((r) => r.json()),
    api("/admin/jobs").then((r) => r.json()),
    api("/admin/users").then((r) => r.json()),
  ]);

  const ratio = stats.avg_realtime_ratio;
  $("tiles").innerHTML = [
    tile("Inférences réalisées", stats.done, `${stats.total} demandes au total`),
    tile("Temps de calcul moyen", fmtSeconds(stats.avg_processing_s), "par traitement terminé"),
    tile("Ratio temps réel", ratio == null ? "—" : `×${ratio.toFixed(2)}`, "calcul / durée du média, doit rester < 1", ratio == null ? "" : ratio < 1 ? "good" : "warn"),
    tile("Non terminés", stats.unfinished, "en attente ou en cours"),
    tile("Échoués", stats.failed, "depuis la mise en service", stats.failed ? "warn" : ""),
  ].join("");

  $("types-body").innerHTML = Object.entries(OUTPUTS).map(([type, o]) => {
    const s = stats.by_type[type];
    return `<tr><td>${o.label}</td><td class="num">${s.total}</td><td class="num">${s.done}</td>
      <td class="num">${s.unfinished}</td><td class="num">${s.failed}</td><td class="num">${fmtSeconds(s.avg_processing_s)}</td></tr>`;
  }).join("");

  $("history-empty").hidden = history.length > 0;
  $("history-body").innerHTML = history.map((job) => `
    <tr>
      <td>${fmtDate(job.created_at)}</td>
      <td>${esc(job.username)}</td>
      <td class="file">${esc(job.original_filename)}</td>
      <td>${OUTPUTS[job.output_type].label}</td>
      <td>${statusChip(job.status)}${job.error_message ? `<span class="err-line">${esc(job.error_message)}</span>` : ""}</td>
      <td class="num">${fmtSeconds(job.processing_time_s)}</td>
      <td>${job.result_text ? `<details><summary>Voir le texte</summary><p>${esc(job.result_text)}</p></details>` : "—"}</td>
    </tr>`).join("");

  $("users-list").innerHTML = users.map((u) => `
    <li><span>${esc(u.username)}</span><span class="chip">${u.role === "admin" ? "Administrateur" : "Utilisateur"}</span></li>`).join("");
}

$("admin-refresh").addEventListener("click", refreshAdmin);

$("user-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = { username: $("new-username").value, password: $("new-password").value, role: $("new-role").value };
  try {
    await api("/admin/users", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    show($("user-msg"), `Compte « ${payload.username} » créé.`);
    event.target.reset();
    await refreshAdmin();
  } catch (error) {
    show($("user-msg"), error.message);
  }
});

renderOutputs();
state.token = loadToken();
if (state.token) {
  startSession().catch(logoutLocal);
} else {
  $("login-view").hidden = false;
}
