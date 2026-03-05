const state = {
  stream: null,
};

const el = {
  authCard: document.getElementById("authCard"),
  email: document.getElementById("emailInput"),
  password: document.getElementById("passwordInput"),
  registerBtn: document.getElementById("registerBtn"),
  loginBtn: document.getElementById("loginBtn"),
  logoutBtn: document.getElementById("logoutBtn"),
  statusPill: document.getElementById("statusPill"),
  commandInput: document.getElementById("commandInput"),
  cpuInput: document.getElementById("cpuInput"),
  ramInput: document.getElementById("ramInput"),
  timeoutInput: document.getElementById("timeoutInput"),
  createBtn: document.getElementById("createBtn"),
  refreshBtn: document.getElementById("refreshBtn"),
  jobsList: document.getElementById("jobsList"),
  jobsEmpty: document.getElementById("jobsEmpty"),
  outputLog: document.getElementById("outputLog"),
  clearOutputBtn: document.getElementById("clearOutputBtn"),
};

function setConnected(flag, text = "") {
  el.statusPill.textContent = text || (flag ? "Connected" : "Disconnected");
  el.statusPill.classList.toggle("connected", flag);
}

function appendOutput(text) {
  const chunk = `${text}\n`;
  if (!el.outputLog.textContent) {
    el.outputLog.textContent = chunk;
  } else {
    el.outputLog.textContent += chunk;
  }
  el.outputLog.scrollTop = el.outputLog.scrollHeight;
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

async function refresh() {
  try {
    await api("/health");
    setConnected(true);
  } catch {
    setConnected(false, "API Offline");
    return;
  }

  try {
    const jobs = await api("/compose-jobs");
    el.authCard.classList.add("hidden");
    renderJobs(jobs);
  } catch (err) {
    el.authCard.classList.remove("hidden");
    if (err.message.includes("401")) {
      setConnected(false, "Not logged in");
      return;
    }
    appendOutput(`Refresh error: ${err.message}`);
  }
}

function stopStream() {
  if (state.stream) {
    state.stream.close();
    state.stream = null;
  }
}

function startStream(composeId) {
  stopStream();
  appendOutput(`--- stream compose ${composeId} ---`);
  const stream = new EventSource(`/compose-jobs/${composeId}/stream`, { withCredentials: true });
  state.stream = stream;
  stream.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      const compose = payload.compose_job;
      appendOutput(`[${compose.updated_at}] status=${compose.status}`);
      if (payload.merged_output) {
        appendOutput(payload.merged_output);
      }
      appendOutput("----------------------------------------");
      if (["completed", "failed", "cancelled"].includes(compose.status)) {
        stopStream();
      }
    } catch (err) {
      appendOutput(`stream parse error: ${err.message}`);
    }
  };
  stream.onerror = () => {
    appendOutput("stream disconnected");
    stopStream();
  };
}

function renderJobs(jobs) {
  el.jobsList.innerHTML = "";
  el.jobsEmpty.style.display = jobs.length ? "none" : "block";
  jobs.forEach((job) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "item selectable";
    item.textContent = `id=${job.id}\nstatus=${job.status}\ncpu_host_id=${job.cpu_host_id}\ngpu_host_id=${job.gpu_host_id}\ncpu_cores=${job.requested_cpu_cores}\nram_mb=${job.requested_ram_mb}\nupdated_at=${job.updated_at}`;
    item.addEventListener("click", () => startStream(job.id));
    el.jobsList.appendChild(item);
  });
}

el.registerBtn.addEventListener("click", async () => {
  try {
    await api("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email: el.email.value.trim(), password: el.password.value, role: "client" }),
    });
    await refresh();
  } catch (err) {
    appendOutput(`Register failed: ${err.message}`);
  }
});

el.loginBtn.addEventListener("click", async () => {
  try {
    await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: el.email.value.trim(), password: el.password.value }),
    });
    await refresh();
  } catch (err) {
    appendOutput(`Login failed: ${err.message}`);
  }
});

el.logoutBtn.addEventListener("click", async () => {
  stopStream();
  try {
    await api("/auth/logout", { method: "POST" });
  } catch (err) {
    appendOutput(`Logout failed: ${err.message}`);
  }
  await refresh();
});

el.createBtn.addEventListener("click", async () => {
  const command = el.commandInput.value.trim();
  if (!command) {
    appendOutput("Command required.");
    return;
  }
  try {
    const result = await api("/compose-jobs", {
      method: "POST",
      body: JSON.stringify({
        command_text: command,
        requested_cpu_cores: Number(el.cpuInput.value),
        requested_ram_mb: Number(el.ramInput.value),
        timeout_seconds: Number(el.timeoutInput.value),
        gpu_required: true,
      }),
    });
    appendOutput(`Compose job created: ${result.compose_job.id}`);
    await refresh();
    startStream(result.compose_job.id);
  } catch (err) {
    appendOutput(`Create compose failed: ${err.message}`);
  }
});

el.refreshBtn.addEventListener("click", refresh);
el.clearOutputBtn.addEventListener("click", () => {
  el.outputLog.textContent = "";
});

refresh();
setInterval(refresh, 2500);
