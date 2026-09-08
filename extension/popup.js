const API_BASE = "http://localhost:8000";

document.addEventListener("DOMContentLoaded", () => {
  initPopup();
});

async function initPopup() {
  const statusDot = document.querySelector("#server-status .dot");
  const statusText = document.getElementById("status-text");
  
  try {
    const res = await fetch(`${API_BASE}/api/stats`);
    if (!res.ok) throw new Error("Server not responding");
    
    const stats = await res.json();
    statusDot.className = "dot online";
    statusText.innerText = "Online";

    updateStatsUI(stats);
    await loadConfig();

  } catch (err) {
    statusDot.className = "dot offline";
    statusText.innerText = "Offline";
    showFeedback("Cannot connect to server at http://localhost:8000. Start python main.py --server", "error");
  }

  setupEventListeners();
}

async function loadConfig() {
  try {
    const res = await fetch(`${API_BASE}/api/config`);
    const cfg = await res.json();

    renderRoleTags(cfg.target_roles || []);
    
    const emailToggle = document.getElementById("email-toggle");
    if (emailToggle && cfg.email) {
      emailToggle.checked = !!cfg.email.send_digest;
    }
  } catch (err) {
    console.error("Failed to load config:", err);
  }
}

function updateStatsUI(stats) {
  document.getElementById("stat-total-jobs").innerText = stats.total_jobs || 0;
  
  let timeStr = "Never";
  if (stats.last_digest_time && stats.last_digest_time !== "Never") {
    try {
      const d = new Date(stats.last_digest_time);
      timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch(e) {}
  }
  document.getElementById("stat-last-digest").innerText = timeStr;
}

function renderRoleTags(roles) {
  const container = document.getElementById("roles-tags-list");
  const countBadge = document.getElementById("role-count");
  
  countBadge.innerText = `${roles.length} active`;
  
  if (roles.length === 0) {
    container.innerHTML = `<span class="placeholder-text">No target roles defined yet. Add one above!</span>`;
    return;
  }

  container.innerHTML = roles.map(role => `
    <div class="tag-chip">
      <span>${role}</span>
      <span class="remove-btn" data-role="${role}">×</span>
    </div>
  `).join("");

  // Attach delete handlers
  container.querySelectorAll(".remove-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const roleToRemove = e.target.getAttribute("data-role");
      removeRole(roleToRemove);
    });
  });
}

function setupEventListeners() {
  // Add role
  const addBtn = document.getElementById("add-role-btn");
  const roleInput = document.getElementById("new-role-input");

  const handleAdd = () => {
    const val = roleInput.value.trim();
    if (val) {
      addRole(val);
      roleInput.value = "";
    }
  };

  addBtn.addEventListener("click", handleAdd);
  roleInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") handleAdd();
  });

  // Email Toggle
  const emailToggle = document.getElementById("email-toggle");
  emailToggle.addEventListener("change", async (e) => {
    try {
      await fetch(`${API_BASE}/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: { send_digest: e.target.checked } })
      });
      showFeedback(`Email alerts ${e.target.checked ? 'enabled' : 'disabled'}!`, "success");
    } catch(err) {
      showFeedback("Failed to update email setting", "error");
    }
  });

  // Send Mail Now Trigger
  document.getElementById("trigger-mail-btn").addEventListener("click", async () => {
    const btn = document.getElementById("trigger-mail-btn");
    btn.disabled = true;
    btn.innerHTML = `<span class="icon">⏳</span><span>Dispatching...</span>`;

    try {
      const res = await fetch(`${API_BASE}/api/send-test-email`, { method: "POST" });
      const data = await res.json();
      showFeedback(data.message, "success");
    } catch (err) {
      showFeedback("Failed to trigger email digest.", "error");
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<span class="icon">✉️</span><span>Send Email Digest Now</span>`;
    }
  });

  // Clip Current Web Page Job
  document.getElementById("clip-job-btn").addEventListener("click", clipCurrentTab);

  // Open Dashboard
  document.getElementById("open-dashboard-btn").addEventListener("click", () => {
    chrome.tabs.create({ url: API_BASE });
  });
}

async function addRole(role) {
  try {
    const res = await fetch(`${API_BASE}/api/roles/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role })
    });
    const data = await res.json();
    renderRoleTags(data.target_roles);
    showFeedback(`Added role: "${role}"`, "success");
  } catch(err) {
    showFeedback("Failed to add role", "error");
  }
}

async function removeRole(role) {
  try {
    const res = await fetch(`${API_BASE}/api/roles/remove`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role })
    });
    const data = await res.json();
    renderRoleTags(data.target_roles);
    showFeedback(`Removed role: "${role}"`, "success");
  } catch(err) {
    showFeedback("Failed to remove role", "error");
  }
}

async function clipCurrentTab() {
  if (typeof chrome === "undefined" || !chrome.tabs) {
    showFeedback("Web clipping works inside Chrome extension!", "error");
    return;
  }

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) return;

    // Send save request
    const jobData = {
      title: tab.title ? tab.title.split("-")[0].split("|")[0].trim() : "Job Listing",
      company: tab.title && tab.title.includes("-") ? tab.title.split("-")[1].trim() : "Web Site",
      location: "Web Clipper",
      url: tab.url,
      source: getDomainName(tab.url),
      status: "Saved",
      notes: `Clipped from tab on ${new Date().toLocaleDateString()}`
    };

    const res = await fetch(`${API_BASE}/api/jobs/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job: jobData })
    });

    if (res.ok) {
      showFeedback(`📌 Saved job "${jobData.title}" to Dashboard!`, "success");
    } else {
      showFeedback("Failed to clip job.", "error");
    }
  } catch(err) {
    showFeedback("Error clipping page: " + err.message, "error");
  }
}

function getDomainName(urlStr) {
  try {
    const u = new URL(urlStr);
    if (u.hostname.includes("linkedin")) return "LinkedIn";
    if (u.hostname.includes("naukri")) return "Naukri";
    if (u.hostname.includes("glassdoor")) return "Glassdoor";
    if (u.hostname.includes("indeed")) return "Indeed";
    return u.hostname.replace("www.", "");
  } catch(e) {
    return "Web Page";
  }
}

function showFeedback(msg, type = "info") {
  const el = document.getElementById("action-feedback");
  el.className = `feedback-msg ${type}`;
  el.innerText = msg;
  el.classList.remove("hidden");
  setTimeout(() => {
    el.classList.add("hidden");
  }, 4000);
}
