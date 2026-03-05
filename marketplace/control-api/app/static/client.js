const state = {
  authenticated: false,
  selectedHostId: "",
};

const el = {
  authCard: document.getElementById("authCard"),
  email: document.getElementById("emailInput"),
  password: document.getElementById("passwordInput"),
  registerBtn: document.getElementById("registerBtn"),
  loginBtn: document.getElementById("loginBtn"),
  topLogoutBtn: document.getElementById("topLogoutBtn"),
  command: document.getElementById("commandInput"),
  timeout: document.getElementById("timeoutInput"),
  requestedCpu: document.getElementById("requestedCpuInput"),
  requestedRam: document.getElementById("requestedRamInput"),
  requiresGpu: document.getElementById("requiresGpuInput"),
  preferredHost: document.getElementById("preferredHostSelect"),
  submitJobBtn: document.getElementById("submitJobBtn"),
  refreshBtn: document.getElementById("refreshBtn"),
  resourcesList: document.getElementById("resourcesList"),
  resourcesEmpty: document.getElementById("resourcesEmpty"),
  jobsList: document.getElementById("jobsList"),
  jobsEmpty: document.getElementById("jobsEmpty"),
  logOutput: document.getElementById("logOutput"),
  statusPill: document.getElementById("statusPill"),
};

function log(message) {
  const stamp = new Date().toLocaleTimeString();
  el.logOutput.textContent = `[${stamp}] ${message}\n${el.logOutput.textContent}`.slice(0, 5000);
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

function setConnected(flag, text = "") {
  el.statusPill.textContent = text || (flag ? "Connected" : "Disconnected");
  el.statusPill.classList.toggle("connected", flag);
}

function setAuthState(authenticated) {
  state.authenticated = authenticated;
  el.authCard.classList.toggle("hidden", authenticated);
  el.topLogoutBtn.classList.toggle("hidden", !authenticated);
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

function renderJobs(jobs) {
  el.jobsList.innerHTML = "";
  el.jobsEmpty.style.display = jobs.length ? "none" : "block";
  jobs
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .forEach((job) => {
      const item = document.createElement("div");
      item.className = "item";
      item.textContent = `id=${job.id}\nstatus=${job.status}\ncommand=${JSON.stringify(job.command)}\nrequested_cpu=${job.requested_cpu_cores}\nrequested_ram_mb=${job.requested_ram_mb}\nrequires_gpu=${job.requires_gpu}\npreferred_host_id=${job.preferred_host_id || "any"}\nassigned_host_id=${job.assigned_host_id || "none"}\nupdated_at=${job.updated_at}`;
      el.jobsList.appendChild(item);
    });
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
    const [hosts, jobs] = await Promise.all([api("/hosts/available"), api("/jobs")]);
    setAuthState(true);
    renderPreferredHostOptions(hosts);
    renderResources(hosts);
    renderJobs(jobs);
  } catch (err) {
    el.resourcesList.innerHTML = "";
    el.jobsList.innerHTML = "";
    el.resourcesEmpty.style.display = "block";
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
  await refreshAll();
});

el.preferredHost.addEventListener("change", () => {
  state.selectedHostId = el.preferredHost.value;
});

el.submitJobBtn.addEventListener("click", async () => {
  let command;
  try {
    command = JSON.parse(el.command.value);
    if (!Array.isArray(command) || !command.length) {
      throw new Error("Command must be a non-empty JSON array.");
    }
  } catch (err) {
    log(`Invalid command: ${err.message}`);
    notify(`Invalid command: ${err.message}`, "error");
    return;
  }
  try {
    const job = await api("/jobs", {
      method: "POST",
      body: JSON.stringify({
        command,
        requires_gpu: el.requiresGpu.checked,
        requested_cpu_cores: Number(el.requestedCpu.value),
        requested_ram_mb: Number(el.requestedRam.value),
        timeout_seconds: Number(el.timeout.value),
        preferred_host_id: state.selectedHostId || null,
      }),
    });
    log(`Job submitted: ${job.id}`);
    notify("Job submitted.", "success");
    await refreshAll();
  } catch (err) {
    log(`Submit failed: ${err.message}`);
    notify(`Submit failed: ${err.message}`, "error");
  }
});

el.refreshBtn.addEventListener("click", refreshAll);

setAuthState(false);
refreshAll();
setInterval(refreshAll, 5000);
