const state = {
  authenticated: false,
  selectedHostId: "",
  selectedJobIds: new Set(),
  uploadedUrl: "",
  retainProgress: localStorage.getItem("marketplace_retain_progress") === "1",
  sessionId: localStorage.getItem("marketplace_session_id") || "",
  terminalConnected: false,
  terminalBusy: false,
  terminalQueue: [],
  activeJobId: null,
  activeOutputLength: 0,
  activeComposeId: null,
  activeComposeOutputLength: 0,
};

const el = {
  authCard: document.getElementById("authCard"),
  email: document.getElementById("emailInput"),
  password: document.getElementById("passwordInput"),
  registerBtn: document.getElementById("registerBtn"),
  loginBtn: document.getElementById("loginBtn"),
  topLogoutBtn: document.getElementById("topLogoutBtn"),
  timeout: document.getElementById("timeoutInput"),
  requestedCpu: document.getElementById("requestedCpuInput"),
  requestedRam: document.getElementById("requestedRamInput"),
  requiresGpu: document.getElementById("requiresGpuInput"),
  crossHostCompose: document.getElementById("crossHostComposeInput"),
  cpuComposeHost: document.getElementById("cpuComposeHostSelect"),
  gpuComposeHost: document.getElementById("gpuComposeHostSelect"),
  retainProgressInput: document.getElementById("retainProgressInput"),
  sessionIdOutput: document.getElementById("sessionIdOutput"),
  preferredHost: document.getElementById("preferredHostSelect"),
  uploadFileInput: document.getElementById("uploadFileInput"),
  uploadFileBtn: document.getElementById("uploadFileBtn"),
  uploadedUrlOutput: document.getElementById("uploadedUrlOutput"),
  insertUrlBtn: document.getElementById("insertUrlBtn"),
  connectTerminalBtn: document.getElementById("connectTerminalBtn"),
  disconnectTerminalBtn: document.getElementById("disconnectTerminalBtn"),
  stopSessionBtn: document.getElementById("stopSessionBtn"),
  terminalCommandInput: document.getElementById("terminalCommandInput"),
  sendCommandBtn: document.getElementById("sendCommandBtn"),
  refreshBtn: document.getElementById("refreshBtn"),
  resourcesList: document.getElementById("resourcesList"),
  resourcesEmpty: document.getElementById("resourcesEmpty"),
  sessionsList: document.getElementById("sessionsList"),
  sessionsEmpty: document.getElementById("sessionsEmpty"),
  jobsList: document.getElementById("jobsList"),
  jobsEmpty: document.getElementById("jobsEmpty"),
  selectAllJobsBtn: document.getElementById("selectAllJobsBtn"),
  clearJobSelectionBtn: document.getElementById("clearJobSelectionBtn"),
  cancelSelectedJobsBtn: document.getElementById("cancelSelectedJobsBtn"),
  deleteSelectedJobsBtn: document.getElementById("deleteSelectedJobsBtn"),
  terminalOutput: document.getElementById("terminalOutput"),
  logOutput: document.getElementById("logOutput"),
  clearTerminalBtn: document.getElementById("clearTerminalBtn"),
  clearActivityBtn: document.getElementById("clearActivityBtn"),
  statusPill: document.getElementById("statusPill"),
};

function log(message) {
  const stamp = new Date().toLocaleTimeString();
  el.logOutput.textContent = `[${stamp}] ${message}\n${el.logOutput.textContent}`.slice(0, 5000);
}

function appendTerminal(text) {
  const chunk = `${text}\n`;
  if (!el.terminalOutput.textContent || el.terminalOutput.textContent === "No terminal output yet.") {
    el.terminalOutput.textContent = chunk;
  } else {
    el.terminalOutput.textContent += chunk;
  }
  el.terminalOutput.scrollTop = el.terminalOutput.scrollHeight;
}

function getToastRoot() {
  let root = document.getElementById("notifications");
  if (!root) {
    root = document.createElement("div");
    root.id = "notifications";
    root.className = "notifications";
    document.body.appendChild(root);
  }
  return root;
}

function notify(message, level = "info") {
  const root = getToastRoot();
  const toast = document.createElement("div");
  toast.className = `toast ${level}`;
  toast.textContent = message;
  root.appendChild(toast);
  setTimeout(() => toast.remove(), 3200);
}

function isAuthError(err) {
  return (
    err.message.includes("401") &&
    (err.message.includes("Missing authentication") || err.message.includes("Invalid token"))
  );
}

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (!headers["Content-Type"] && options.body) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, { credentials: "same-origin", ...options, headers });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(`${response.status}: ${data.detail || response.statusText}`);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

async function uploadFile(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/files/upload", {
    method: "POST",
    credentials: "same-origin",
    body: formData,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(`${response.status}: ${data.detail || response.statusText}`);
  }
  return response.json();
}

function setConnected(flag, text = "") {
  el.statusPill.textContent = text || (flag ? "Connected" : "Disconnected");
  el.statusPill.classList.toggle("connected", flag);
}

function setAuthState(authenticated) {
  state.authenticated = authenticated;
  el.authCard.classList.toggle("hidden", authenticated);
  el.topLogoutBtn.classList.toggle("hidden", !authenticated);
}

function persistSessionState() {
  localStorage.setItem("marketplace_retain_progress", state.retainProgress ? "1" : "0");
  if (state.sessionId) {
    localStorage.setItem("marketplace_session_id", state.sessionId);
  } else {
    localStorage.removeItem("marketplace_session_id");
  }
}

function refreshTerminalButtons() {
  el.connectTerminalBtn.disabled = state.terminalConnected;
  el.disconnectTerminalBtn.disabled = !state.terminalConnected;
  el.sendCommandBtn.disabled = !state.terminalConnected;
  el.stopSessionBtn.disabled = !state.sessionId;
}

function generateSessionId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  return `sess-${Date.now()}-${Math.floor(Math.random() * 100000)}`;
}

function renderPreferredHostOptions(hosts) {
  const current = state.selectedHostId;
  el.preferredHost.innerHTML = "";

  const anyOption = document.createElement("option");
  anyOption.value = "";
  anyOption.textContent = "Any Available Host";
  el.preferredHost.appendChild(anyOption);

  hosts.forEach((host) => {
    const option = document.createElement("option");
    option.value = host.id;
    option.textContent = `${host.host_name} (${host.status}, ${host.cpu_cores_free}/${host.cpu_cores}C free, ${host.ram_mb_free}/${host.ram_mb}MB free${host.gpu_name ? ", GPU" : ""})`;
    el.preferredHost.appendChild(option);
  });

  if (current && hosts.some((host) => host.id === current)) {
    el.preferredHost.value = current;
  } else {
    state.selectedHostId = "";
    el.preferredHost.value = "";
  }
}

function composeHostLabel(host) {
  return `${host.host_name} (${host.cpu_cores_free}/${host.cpu_cores}C, ${host.ram_mb_free}/${host.ram_mb}MB${host.gpu_name ? ", GPU" : ""})`;
}

function renderComposeHostOptions(hosts) {
  const cpuValue = el.cpuComposeHost.value || "";
  const gpuValue = el.gpuComposeHost.value || "";

  el.cpuComposeHost.innerHTML = "";
  el.gpuComposeHost.innerHTML = "";

  const autoCpu = document.createElement("option");
  autoCpu.value = "";
  autoCpu.textContent = "Auto";
  el.cpuComposeHost.appendChild(autoCpu);

  const autoGpu = document.createElement("option");
  autoGpu.value = "";
  autoGpu.textContent = "Auto";
  el.gpuComposeHost.appendChild(autoGpu);

  hosts.filter((host) => host.verified).forEach((host) => {
    const option = document.createElement("option");
    option.value = host.id;
    option.textContent = composeHostLabel(host);
    el.cpuComposeHost.appendChild(option);
  });

  hosts.filter((host) => host.verified && host.gpu_name).forEach((host) => {
    const option = document.createElement("option");
    option.value = host.id;
    option.textContent = composeHostLabel(host);
    el.gpuComposeHost.appendChild(option);
  });

  el.cpuComposeHost.value = [...el.cpuComposeHost.options].some((o) => o.value === cpuValue) ? cpuValue : "";
  el.gpuComposeHost.value = [...el.gpuComposeHost.options].some((o) => o.value === gpuValue) ? gpuValue : "";
}

function renderResources(hosts) {
  el.resourcesList.innerHTML = "";
  el.resourcesEmpty.style.display = hosts.length ? "none" : "block";
  hosts.forEach((host) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "item selectable";
    if (host.id === state.selectedHostId) {
      item.classList.add("selected");
    }
    item.textContent = `name=${host.host_name}\nstatus=${host.status}\ncpu_free=${host.cpu_cores_free}/${host.cpu_cores}\nram_free_mb=${host.ram_mb_free}/${host.ram_mb}\ngpu_name=${host.gpu_name || "none"}\nvram_mb=${host.vram_mb || "unknown"}\nlast_seen_at=${host.last_seen_at}`;
    item.addEventListener("click", () => {
      state.selectedHostId = host.id;
      el.preferredHost.value = host.id;
      renderResources(hosts);
      notify(`Preferred host selected: ${host.host_name}`, "success");
    });
    el.resourcesList.appendChild(item);
  });
}

function renderSessions(sessions) {
  el.sessionsList.innerHTML = "";
  el.sessionsEmpty.style.display = sessions.length ? "none" : "block";
  const ids = new Set(sessions.map((s) => s.session_id));
  if (state.sessionId && !ids.has(state.sessionId)) {
    state.sessionId = "";
    el.sessionIdOutput.value = "";
    persistSessionState();
  }
  sessions.forEach((session) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "item selectable";
    if (session.session_id === state.sessionId) {
      item.classList.add("selected");
    }
    item.textContent = `session_id=${session.session_id}\nhost_id=${session.host_id}\ncpu_cores=${session.cpu_cores}\nram_mb=${session.ram_mb}\nrequires_gpu=${session.requires_gpu}`;
    item.addEventListener("click", () => {
      state.sessionId = session.session_id;
      state.retainProgress = true;
      el.retainProgressInput.checked = true;
      el.sessionIdOutput.value = state.sessionId;
      persistSessionState();
      refreshTerminalButtons();
      renderSessions(sessions);
      notify(`Selected session ${session.session_id}`, "success");
    });
    el.sessionsList.appendChild(item);
  });
}

function renderJobs(jobs) {
  el.jobsList.innerHTML = "";
  const availableIds = new Set(jobs.map((job) => job.id));
  state.selectedJobIds = new Set([...state.selectedJobIds].filter((id) => availableIds.has(id)));
  el.jobsEmpty.style.display = jobs.length ? "none" : "block";
  jobs
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .forEach((job) => {
      const item = document.createElement("div");
      item.className = "item";
      const canCancel = !["completed", "failed", "cancelled", "expired"].includes(job.status);
      const isSelected = state.selectedJobIds.has(job.id);

      const topRow = document.createElement("div");
      topRow.className = "row";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = isSelected;
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) {
          state.selectedJobIds.add(job.id);
        } else {
          state.selectedJobIds.delete(job.id);
        }
      });

      const cancelBtn = document.createElement("button");
      cancelBtn.type = "button";
      cancelBtn.className = "btn ghost";
      cancelBtn.textContent = "Cancel";
      cancelBtn.disabled = !canCancel;
      cancelBtn.addEventListener("click", async () => {
        await cancelJob(job.id);
      });

      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "btn ghost";
      deleteBtn.textContent = "Delete";
      deleteBtn.addEventListener("click", async () => {
        await deleteJob(job.id);
      });

      topRow.appendChild(checkbox);
      topRow.appendChild(cancelBtn);
      topRow.appendChild(deleteBtn);
      item.appendChild(topRow);

      const details = document.createElement("pre");
      details.textContent = `id=${job.id}\nmode=${job.mode}\nstatus=${job.status}\nsession_id=${job.session_id || "none"}\nretain_progress=${job.retain_progress}\nsession_action=${job.session_action}\ncommand=${JSON.stringify(job.command)}\nrequested_cpu=${job.requested_cpu_cores}\nrequested_ram_mb=${job.requested_ram_mb}\nrequires_gpu=${job.requires_gpu}\npreferred_host_id=${job.preferred_host_id || "any"}\nassigned_host_id=${job.assigned_host_id || "none"}\nreserve_until=${job.reserve_until || "n/a"}\nupdated_at=${job.updated_at}`;
      item.appendChild(details);
      el.jobsList.appendChild(item);
    });
}

function insertUploadedUrlIntoCommand() {
  if (!state.uploadedUrl) {
    notify("No uploaded file URL yet.", "error");
    return;
  }
  const existing = el.terminalCommandInput.value.trim();
  el.terminalCommandInput.value = existing ? `${existing} ${state.uploadedUrl}` : state.uploadedUrl;
  notify("Uploaded URL inserted into command.", "success");
}

function updateActiveJobOutput(jobs) {
  if (state.activeComposeId) {
    return;
  }
  if (!state.activeJobId) {
    return;
  }
  const active = jobs.find((job) => job.id === state.activeJobId);
  if (!active) {
    state.terminalBusy = false;
    state.activeJobId = null;
    state.activeOutputLength = 0;
    refreshTerminalButtons();
    processNextQueuedCommand();
    return;
  }

  const output = active.output || "";
  if (output.length > state.activeOutputLength) {
    const delta = output.slice(state.activeOutputLength);
    appendTerminal(delta);
    state.activeOutputLength = output.length;
  }

  if (["completed", "failed", "cancelled", "expired"].includes(active.status)) {
    appendTerminal(`[exit=${active.exit_code ?? "n/a"}] status=${active.status}`);
    state.terminalBusy = false;
    state.activeJobId = null;
    state.activeOutputLength = 0;
    refreshTerminalButtons();
    processNextQueuedCommand();
  }
}

async function updateActiveComposeOutput() {
  if (!state.activeComposeId) {
    return;
  }
  let detail;
  try {
    detail = await api(`/compose-jobs/${state.activeComposeId}/status`);
  } catch (err) {
    state.terminalBusy = false;
    state.activeComposeId = null;
    state.activeComposeOutputLength = 0;
    refreshTerminalButtons();
    log(`Compose refresh failed: ${err.message}`);
    processNextQueuedCommand();
    return;
  }

  const merged = detail.merged_output || "";
  if (merged.length > state.activeComposeOutputLength) {
    const delta = merged.slice(state.activeComposeOutputLength);
    appendTerminal(delta);
    state.activeComposeOutputLength = merged.length;
  }

  const composeStatus = detail.compose_job?.status || "failed";
  if (["completed", "failed", "cancelled"].includes(composeStatus)) {
    appendTerminal(`[compose status=${composeStatus}]`);
    state.terminalBusy = false;
    state.activeComposeId = null;
    state.activeComposeOutputLength = 0;
    refreshTerminalButtons();
    processNextQueuedCommand();
  }
}

async function refreshAll() {
  try {
    await api("/health");
    setConnected(true);
  } catch {
    setConnected(false, "API Offline");
    return;
  }
  try {
    const [hosts, sessions, jobs] = await Promise.all([api("/hosts/available"), api("/jobs/sessions"), api("/jobs")]);
    setAuthState(true);
    renderPreferredHostOptions(hosts);
    renderComposeHostOptions(hosts);
    renderResources(hosts);
    renderSessions(sessions);
    renderJobs(jobs);
    updateActiveJobOutput(jobs);
    await updateActiveComposeOutput();
  } catch (err) {
    el.resourcesList.innerHTML = "";
    el.sessionsList.innerHTML = "";
    el.jobsList.innerHTML = "";
    el.resourcesEmpty.style.display = "block";
    el.sessionsEmpty.style.display = "block";
    el.jobsEmpty.style.display = "block";
    if (isAuthError(err)) {
      setAuthState(false);
      setConnected(false, "Not logged in");
      return;
    }
    log(`Refresh failed: ${err.message}`);
    notify(`Refresh failed: ${err.message}`, "error");
  }
}

el.registerBtn.addEventListener("click", async () => {
  try {
    await api("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email: el.email.value.trim(), password: el.password.value, role: "client" }),
    });
    log("Client registered and session started.");
    notify("Client registered.", "success");
    await refreshAll();
  } catch (err) {
    log(`Register failed: ${err.message}`);
    notify(`Register failed: ${err.message}`, "error");
  }
});

el.loginBtn.addEventListener("click", async () => {
  try {
    await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: el.email.value.trim(), password: el.password.value }),
    });
    log("Login succeeded.");
    notify("Login succeeded.", "success");
    await refreshAll();
  } catch (err) {
    log(`Login failed: ${err.message}`);
    notify(`Login failed: ${err.message}`, "error");
  }
});

el.topLogoutBtn.addEventListener("click", async () => {
  try {
    await api("/auth/logout", { method: "POST" });
    log("Logged out.");
    notify("Logged out.", "info");
  } catch (err) {
    log(`Logout failed: ${err.message}`);
    notify(`Logout failed: ${err.message}`, "error");
  }
  setAuthState(false);
  state.selectedHostId = "";
  state.terminalConnected = false;
  state.terminalBusy = false;
  state.terminalQueue = [];
  state.activeJobId = null;
  state.activeOutputLength = 0;
  state.activeComposeId = null;
  state.activeComposeOutputLength = 0;
  refreshTerminalButtons();
  await refreshAll();
});

el.preferredHost.addEventListener("change", () => {
  state.selectedHostId = el.preferredHost.value;
});

el.connectTerminalBtn.addEventListener("click", () => {
  state.terminalConnected = true;
  state.retainProgress = !!el.retainProgressInput.checked;
  if (state.retainProgress && !state.sessionId) {
    state.sessionId = generateSessionId();
    el.sessionIdOutput.value = state.sessionId;
  }
  if (!state.retainProgress) {
    state.sessionId = "";
    el.sessionIdOutput.value = "";
  }
  persistSessionState();
  refreshTerminalButtons();
  appendTerminal("[terminal connected]");
  notify("Terminal connected.", "success");
  el.terminalCommandInput.focus();
});

el.disconnectTerminalBtn.addEventListener("click", () => {
  state.terminalConnected = false;
  state.terminalBusy = false;
  state.terminalQueue = [];
  state.activeJobId = null;
  state.activeOutputLength = 0;
  state.activeComposeId = null;
  state.activeComposeOutputLength = 0;
  refreshTerminalButtons();
  appendTerminal("[terminal disconnected]");
  notify("Terminal disconnected.", "info");
});

el.retainProgressInput.addEventListener("change", () => {
  state.retainProgress = !!el.retainProgressInput.checked;
  if (state.retainProgress && !state.sessionId) {
    state.sessionId = generateSessionId();
    el.sessionIdOutput.value = state.sessionId;
  }
  if (!state.retainProgress && !state.terminalConnected) {
    state.sessionId = "";
    el.sessionIdOutput.value = "";
  }
  persistSessionState();
  refreshTerminalButtons();
});

async function submitSingleCommand(commandText) {
  try {
    if (el.crossHostCompose.checked) {
      if (!el.requiresGpu.checked) {
        throw new Error("Split mode requires 'Requires GPU' to be enabled.");
      }
      const compose = await api("/compose-jobs", {
        method: "POST",
        body: JSON.stringify({
          command_text: commandText,
          requested_cpu_cores: Number(el.requestedCpu.value),
          requested_ram_mb: Number(el.requestedRam.value),
          timeout_seconds: Number(el.timeout.value),
          gpu_required: true,
          cpu_host_id: el.cpuComposeHost.value || null,
          gpu_host_id: el.gpuComposeHost.value || null,
        }),
      });

      state.terminalBusy = true;
      state.activeJobId = null;
      state.activeOutputLength = 0;
      state.activeComposeId = compose.compose_job.id;
      state.activeComposeOutputLength = 0;
      refreshTerminalButtons();
      log(`Split compose command submitted: ${compose.compose_job.id}`);
      await refreshAll();
      return;
    }

    const job = await api("/jobs", {
      method: "POST",
      body: JSON.stringify({
        mode: "quick_run",
        command_text: commandText,
        session_id: state.retainProgress ? state.sessionId : null,
        retain_progress: state.retainProgress,
        requires_gpu: el.requiresGpu.checked,
        requested_cpu_cores: Number(el.requestedCpu.value),
        requested_ram_mb: Number(el.requestedRam.value),
        timeout_seconds: Number(el.timeout.value),
        reserve_seconds: 120,
        preferred_host_id: state.selectedHostId || null,
      }),
    });

    state.terminalBusy = true;
    state.activeJobId = job.id;
    state.activeOutputLength = 0;
    state.activeComposeId = null;
    state.activeComposeOutputLength = 0;
    refreshTerminalButtons();
    log(`Terminal command submitted: ${job.id}`);
    await refreshAll();
  } catch (err) {
    state.terminalBusy = false;
    refreshTerminalButtons();
    log(`Submit failed: ${err.message}`);
    notify(`Submit failed: ${err.message}`, "error");
    processNextQueuedCommand();
  }
}

function processNextQueuedCommand() {
  if (!state.terminalConnected || state.terminalBusy) {
    return;
  }
  const nextCommand = state.terminalQueue.shift();
  if (!nextCommand) {
    return;
  }
  appendTerminal(`> ${nextCommand}`);
  submitSingleCommand(nextCommand);
}

function runTerminalCommand() {
  if (!state.terminalConnected) {
    notify("Connect terminal first.", "error");
    return;
  }

  const commands = el.terminalCommandInput.value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (!commands.length) {
    notify("Add at least one command.", "error");
    return;
  }
  if (state.retainProgress && !state.sessionId) {
    state.sessionId = generateSessionId();
    el.sessionIdOutput.value = state.sessionId;
    persistSessionState();
  }

  state.terminalQueue.push(...commands);
  el.terminalCommandInput.value = "";
  processNextQueuedCommand();
}

async function stopRetainedSession() {
  if (!state.sessionId) {
    notify("No retained session is active.", "info");
    return;
  }
  try {
    await api(`/jobs/sessions/${state.sessionId}/stop`, {
      method: "POST",
      body: JSON.stringify({
        preferred_host_id: state.selectedHostId || null,
        requires_gpu: el.requiresGpu.checked,
      }),
    });
    appendTerminal(`[session stop requested] ${state.sessionId}`);
    log(`Session stop requested: ${state.sessionId}`);
    state.sessionId = "";
    el.sessionIdOutput.value = "";
    persistSessionState();
    refreshTerminalButtons();
  } catch (err) {
    notify(`Stop session failed: ${err.message}`, "error");
  }
}

async function cancelJob(jobId) {
  try {
    await api(`/jobs/${jobId}/cancel`, { method: "POST" });
    log(`Job cancelled: ${jobId}`);
    notify("Job cancelled.", "success");
    await refreshAll();
  } catch (err) {
    log(`Cancel failed: ${err.message}`);
    notify(`Cancel failed: ${err.message}`, "error");
  }
}

async function deleteJob(jobId) {
  try {
    await api(`/jobs/${jobId}`, { method: "DELETE" });
    state.selectedJobIds.delete(jobId);
    log(`Job deleted: ${jobId}`);
    notify("Job deleted.", "success");
    await refreshAll();
  } catch (err) {
    log(`Delete failed: ${err.message}`);
    notify(`Delete failed: ${err.message}`, "error");
  }
}

el.sendCommandBtn.addEventListener("click", runTerminalCommand);
el.stopSessionBtn.addEventListener("click", stopRetainedSession);

el.refreshBtn.addEventListener("click", refreshAll);
el.selectAllJobsBtn.addEventListener("click", async () => {
  try {
    const jobs = await api("/jobs");
    jobs.forEach((job) => state.selectedJobIds.add(job.id));
    renderJobs(jobs);
  } catch (err) {
    notify(`Select all failed: ${err.message}`, "error");
  }
});
el.clearJobSelectionBtn.addEventListener("click", () => {
  state.selectedJobIds.clear();
  refreshAll();
});
el.cancelSelectedJobsBtn.addEventListener("click", async () => {
  const ids = [...state.selectedJobIds];
  if (!ids.length) {
    notify("No jobs selected.", "info");
    return;
  }
  for (const id of ids) {
    await cancelJob(id);
  }
});
el.deleteSelectedJobsBtn.addEventListener("click", async () => {
  const ids = [...state.selectedJobIds];
  if (!ids.length) {
    notify("No jobs selected.", "info");
    return;
  }
  for (const id of ids) {
    await deleteJob(id);
  }
  state.selectedJobIds.clear();
});
el.clearTerminalBtn.addEventListener("click", () => {
  el.terminalOutput.textContent = "No terminal output yet.";
});
el.clearActivityBtn.addEventListener("click", () => {
  el.logOutput.textContent = "";
});
el.insertUrlBtn.addEventListener("click", insertUploadedUrlIntoCommand);
el.uploadFileBtn.addEventListener("click", async () => {
  const file = el.uploadFileInput.files && el.uploadFileInput.files[0];
  if (!file) {
    notify("Pick a file first.", "error");
    return;
  }
  try {
    const data = await uploadFile(file);
    state.uploadedUrl = data.download_url;
    el.uploadedUrlOutput.value = state.uploadedUrl;
    notify("File uploaded successfully.", "success");
  } catch (err) {
    notify(`Upload failed: ${err.message}`, "error");
  }
});

setAuthState(false);
el.retainProgressInput.checked = state.retainProgress;
el.sessionIdOutput.value = state.sessionId;
refreshTerminalButtons();
refreshAll();
setInterval(refreshAll, 800);
