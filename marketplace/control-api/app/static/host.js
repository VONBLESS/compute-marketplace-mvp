const state = {
  hostApiKey: localStorage.getItem("marketplace_host_api_key") || "",
};

const el = {
  email: document.getElementById("emailInput"),
  password: document.getElementById("passwordInput"),
  registerBtn: document.getElementById("registerBtn"),
  loginBtn: document.getElementById("loginBtn"),
  logoutBtn: document.getElementById("logoutBtn"),
  detectBtn: document.getElementById("detectBtn"),
  hostName: document.getElementById("hostNameInput"),
  cpu: document.getElementById("cpuInput"),
  ram: document.getElementById("ramInput"),
  gpu: document.getElementById("gpuInput"),
  vram: document.getElementById("vramInput"),
  registerHostBtn: document.getElementById("registerHostBtn"),
  refreshBtn: document.getElementById("refreshBtn"),
  hostApiKey: document.getElementById("hostApiKeyInput"),
  hostsList: document.getElementById("hostsList"),
  hostsEmpty: document.getElementById("hostsEmpty"),
  logOutput: document.getElementById("logOutput"),
  statusPill: document.getElementById("statusPill"),
};

function persist() {
  localStorage.setItem("marketplace_host_api_key", state.hostApiKey);
}

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

function detectGpuName() {
  const canvas = document.createElement("canvas");
  const gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
  if (!gl) {
    return "";
  }
  const debugInfo = gl.getExtension("WEBGL_debug_renderer_info");
  if (!debugInfo) {
    return "";
  }
  const renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
  return typeof renderer === "string" ? renderer : "";
}

function autoDetectHardware() {
  const cpuCores = navigator.hardwareConcurrency || 4;
  const ramGb = navigator.deviceMemory || 8;
  const gpuName = detectGpuName();
  const baseName = navigator.userAgent.includes("Windows") ? "windows-host" : "browser-host";

  el.hostName.value = `${baseName}-${cpuCores}c`;
  el.cpu.value = String(cpuCores);
  el.ram.value = String(ramGb * 1024);
  el.gpu.value = gpuName;
  if (!gpuName) {
    el.gpu.placeholder = "GPU not detectable by browser";
  }
  log(`Hardware detected: ${cpuCores} cores, ${ramGb} GB RAM${gpuName ? `, GPU ${gpuName}` : ""}`);
  notify("Hardware auto-detected.", "success");
}

function renderHosts(hosts) {
  el.hostsList.innerHTML = "";
  el.hostsEmpty.style.display = hosts.length ? "none" : "block";
  hosts.forEach((host) => {
    const item = document.createElement("div");
    item.className = "item";
    item.textContent = `name=${host.host_name}\nid=${host.id}\nstatus=${host.status}\ncpu_free=${host.cpu_cores_free}/${host.cpu_cores}\nram_free_mb=${host.ram_mb_free}/${host.ram_mb}\ngpu_name=${host.gpu_name || "none"}\napi_key=${host.api_key}\nlast_seen_at=${host.last_seen_at}`;
    el.hostsList.appendChild(item);
  });
}

async function refreshHosts() {
  try {
    await api("/health");
    setConnected(true);
  } catch {
    setConnected(false, "API Offline");
    return;
  }
  try {
    const hosts = await api("/hosts");
    renderHosts(hosts);
  } catch (err) {
    el.hostsList.innerHTML = "";
    el.hostsEmpty.style.display = "block";
    if (isAuthError(err)) {
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
      body: JSON.stringify({ email: el.email.value.trim(), password: el.password.value, role: "host" }),
    });
    log("Host user registered and session started.");
    notify("Host user registered.", "success");
    await refreshHosts();
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
    await refreshHosts();
  } catch (err) {
    log(`Login failed: ${err.message}`);
    notify(`Login failed: ${err.message}`, "error");
  }
});

el.logoutBtn.addEventListener("click", async () => {
  try {
    await api("/auth/logout", { method: "POST" });
    log("Logged out.");
    notify("Logged out.", "info");
  } catch (err) {
    log(`Logout failed: ${err.message}`);
    notify(`Logout failed: ${err.message}`, "error");
  }
  await refreshHosts();
});

el.detectBtn.addEventListener("click", autoDetectHardware);

el.registerHostBtn.addEventListener("click", async () => {
  try {
    const host = await api("/hosts/register", {
      method: "POST",
      body: JSON.stringify({
        host_name: el.hostName.value.trim() || "auto-host",
        cpu_cores: Number(el.cpu.value),
        ram_mb: Number(el.ram.value),
        gpu_name: el.gpu.value.trim() || null,
        vram_mb: el.vram.value ? Number(el.vram.value) : null,
      }),
    });
    state.hostApiKey = host.api_key;
    persist();
    el.hostApiKey.value = state.hostApiKey;
    log(`Host registered. API key captured for agent: ${host.api_key}`);
    notify("Host registered successfully.", "success");
    await refreshHosts();
  } catch (err) {
    log(`Host registration failed: ${err.message}`);
    notify(`Host registration failed: ${err.message}`, "error");
  }
});

el.refreshBtn.addEventListener("click", refreshHosts);

el.hostApiKey.value = state.hostApiKey;
autoDetectHardware();
refreshHosts();
setInterval(refreshHosts, 5000);
