const state = {
  hostApiKey: localStorage.getItem("marketplace_host_api_key") || "",
};

const el = {
  email: document.getElementById("emailInput"),
  password: document.getElementById("passwordInput"),
  role: document.getElementById("roleSelect"),
  session: document.getElementById("sessionInput"),
  hostName: document.getElementById("hostNameInput"),
  cpu: document.getElementById("cpuInput"),
  ram: document.getElementById("ramInput"),
  gpu: document.getElementById("gpuInput"),
  hostApiKey: document.getElementById("hostApiKeyInput"),
  command: document.getElementById("commandInput"),
  timeout: document.getElementById("timeoutInput"),
  requiresGpu: document.getElementById("requiresGpuInput"),
  registerBtn: document.getElementById("registerBtn"),
  loginBtn: document.getElementById("loginBtn"),
  logoutBtn: document.getElementById("logoutBtn"),
  registerHostBtn: document.getElementById("registerHostBtn"),
  submitJobBtn: document.getElementById("submitJobBtn"),
  refreshAllBtn: document.getElementById("refreshAllBtn"),
  jobsEmpty: document.getElementById("jobsEmpty"),
  hostsEmpty: document.getElementById("hostsEmpty"),
  jobsList: document.getElementById("jobsList"),
  hostsList: document.getElementById("hostsList"),
  logOutput: document.getElementById("logOutput"),
  statusPill: document.getElementById("statusPill"),
};

function log(message) {
  const stamp = new Date().toLocaleTimeString();
  el.logOutput.textContent = `[${stamp}] ${message}\n${el.logOutput.textContent}`.slice(0, 5000);
}

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (!headers["Content-Type"] && options.body) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, { credentials: "same-origin", ...options, headers });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = data.detail || response.statusText;
    throw new Error(`${response.status}: ${detail}`);
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

function syncFields() {
  el.session.value = "Browser session cookie";
  el.hostApiKey.value = state.hostApiKey;
}

function persist() {
  localStorage.setItem("marketplace_host_api_key", state.hostApiKey);
}

function renderJobs(jobs) {
  el.jobsList.innerHTML = "";
  el.jobsEmpty.style.display = jobs.length ? "none" : "block";
  jobs
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .forEach((job) => {
      const item = document.createElement("div");
      item.className = "item";
      item.textContent = `id=${job.id}\nstatus=${job.status}\ncommand=${JSON.stringify(job.command)}\nassigned_host_id=${job.assigned_host_id || "none"}\nupdated_at=${job.updated_at}`;
      el.jobsList.appendChild(item);
    });
}

function renderHosts(hosts) {
  el.hostsList.innerHTML = "";
  el.hostsEmpty.style.display = hosts.length ? "none" : "block";
  hosts.forEach((host) => {
    const item = document.createElement("div");
    item.className = "item";
    item.textContent = `name=${host.host_name}\nid=${host.id}\nstatus=${host.status}\nlast_seen_at=${host.last_seen_at}\napi_key=${host.api_key}`;
    el.hostsList.appendChild(item);
  });
}

async function checkHealth() {
  try {
    await api("/health");
    setConnected(true);
  } catch (err) {
    setConnected(false, "API Offline");
    log(`Health check failed: ${err.message}`);
  }
}

async function refreshAll() {
  await checkHealth();
  try {
    const [jobs, hosts] = await Promise.all([api("/jobs"), api("/hosts")]);
    renderJobs(jobs);
    renderHosts(hosts);
  } catch (err) {
    el.jobsList.innerHTML = "";
    el.hostsList.innerHTML = "";
    el.jobsEmpty.style.display = "block";
    el.hostsEmpty.style.display = "block";
    log(`Refresh failed: ${err.message}`);
  }
}

el.registerBtn.addEventListener("click", async () => {
  try {
    await api("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email: el.email.value.trim(),
        password: el.password.value,
        role: el.role.value,
      }),
    });
    persist();
    syncFields();
    log("Register succeeded; session started.");
    await refreshAll();
  } catch (err) {
    log(`Register failed: ${err.message}`);
  }
});

el.loginBtn.addEventListener("click", async () => {
  try {
    await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: el.email.value.trim(),
        password: el.password.value,
      }),
    });
    persist();
    syncFields();
    log("Login succeeded; session restored.");
    await refreshAll();
  } catch (err) {
    log(`Login failed: ${err.message}`);
  }
});

el.logoutBtn.addEventListener("click", async () => {
  try {
    await api("/auth/logout", { method: "POST" });
    log("Logged out.");
  } catch (err) {
    log(`Logout failed: ${err.message}`);
  }
  refreshAll();
});

el.registerHostBtn.addEventListener("click", async () => {
  try {
    const data = await api("/hosts/register", {
      method: "POST",
      body: JSON.stringify({
        host_name: el.hostName.value.trim(),
        cpu_cores: Number(el.cpu.value),
        ram_mb: Number(el.ram.value),
        gpu_name: el.gpu.value.trim() || null,
        vram_mb: null,
      }),
    });
    state.hostApiKey = data.api_key;
    persist();
    syncFields();
    log(`Host registered: ${data.host_name}`);
    await refreshAll();
  } catch (err) {
    log(`Host registration failed: ${err.message}`);
  }
});

el.submitJobBtn.addEventListener("click", async () => {
  let command;
  try {
    command = JSON.parse(el.command.value);
    if (!Array.isArray(command) || !command.length) {
      throw new Error("Command must be a non-empty JSON list.");
    }
  } catch (err) {
    log(`Invalid command field: ${err.message}`);
    return;
  }

  try {
    const data = await api("/jobs", {
      method: "POST",
      body: JSON.stringify({
        command,
        requires_gpu: el.requiresGpu.checked,
        timeout_seconds: Number(el.timeout.value),
      }),
    });
    log(`Job submitted: ${data.id}`);
    await refreshAll();
  } catch (err) {
    log(`Submit failed: ${err.message}`);
  }
});

el.refreshAllBtn.addEventListener("click", refreshAll);

syncFields();
refreshAll();
setInterval(refreshAll, 5000);
