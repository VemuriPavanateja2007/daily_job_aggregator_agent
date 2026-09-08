/* ==========================================================================
   JOB DIGEST STUDIO - STEP-BY-STEP WORKFLOW APPLICATION CONTROLLER
   ========================================================================== */

const API_BASE = "";

// State Management
let state = {
  currentStep: 1,
  currentUser: null,
  selectedRoles: ["Machine Learning Engineer", "Data Scientist", "Software Engineer"],
  selectedLocations: ["Remote", "India"],
  enabledPlatforms: { linkedin: true, naukri: true, glassdoor: true },
  jobs: [],
  savedJobs: [],
  lastEmailResult: null
};

document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

async function initApp() {
  setupEventListeners();
  await checkBackendStatus();
  await loadInitialConfig();
  
  // Check if session exists in localStorage
  const savedUser = localStorage.getItem("job_studio_user");
  if (savedUser) {
    try {
      state.currentUser = JSON.parse(savedUser);
      updateUserUI();
      // Auto advance to Step 2 if already logged in
      setStep(2);
    } catch(e) {
      setStep(1);
    }
  } else {
    setStep(1);
  }
}

/* ----------------------------------------------------
   1. WORKFLOW STEP NAVIGATION CONTROL
---------------------------------------------------- */
function setStep(stepNum) {
  // Prevent skipping past login if not logged in
  if (stepNum > 1 && !state.currentUser) {
    showToast("Please sign in first to access target role configuration.", "warning");
    stepNum = 1;
  }

  state.currentStep = stepNum;

  // Update Wizard Header Bar
  const steps = document.querySelectorAll(".wizard-step");
  steps.forEach(s => {
    const sNum = parseInt(s.dataset.step, 10);
    s.classList.remove("active", "completed");
    if (sNum === stepNum) {
      s.classList.add("active");
    } else if (sNum < stepNum) {
      s.classList.add("completed");
    }
  });

  // Update Pane Display
  const panes = document.querySelectorAll(".step-pane");
  panes.forEach(p => p.classList.remove("active"));

  const targetPane = document.getElementById(`pane-step-${stepNum}`);
  if (targetPane) {
    targetPane.classList.add("active");
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // Trigger Step Specific Initialization
  if (stepNum === 2) {
    renderPresetChips();
    renderSelectedRolesPills();
  } else if (stepNum === 3) {
    performJobSearch();
  } else if (stepNum === 4) {
    initEmailStep();
  }
}

/* ----------------------------------------------------
   2. AUTHENTICATION & LOGIN (STEP 1)
---------------------------------------------------- */
async function handleLogin(email, password) {
  try {
    const res = await fetch(`${API_BASE}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (data.status === "success") {
      state.currentUser = data.user;
      localStorage.setItem("job_studio_user", JSON.stringify(data.user));
      updateUserUI();
      showToast(`Welcome back, ${data.user.name}!`, "success");
      setStep(2);
    } else {
      showToast("Invalid credentials. Please try again.", "error");
    }
  } catch(err) {
    console.error("Login failed:", err);
    // Local fallback login for offline/demo resilience
    state.currentUser = { email: email || "user@example.com", name: (email || "Developer").split("@")[0] };
    localStorage.setItem("job_studio_user", JSON.stringify(state.currentUser));
    updateUserUI();
    showToast("Signed in in Demo Mode!", "success");
    setStep(2);
  }
}

function updateUserUI() {
  const profilePill = document.getElementById("user-profile-pill");
  const avatarInitial = document.getElementById("user-avatar-initial");
  const displayName = document.getElementById("user-display-name");
  const displayEmail = document.getElementById("user-display-email");

  if (state.currentUser) {
    profilePill.classList.remove("hidden");
    displayName.innerText = state.currentUser.name;
    displayEmail.innerText = state.currentUser.email;
    avatarInitial.innerText = (state.currentUser.name[0] || "U").toUpperCase();

    // Set default recipient email input
    const emailInput = document.getElementById("recipient-email-input");
    if (emailInput) emailInput.value = state.currentUser.email;
  } else {
    profilePill.classList.add("hidden");
  }
}

function handleLogout() {
  state.currentUser = null;
  localStorage.removeItem("job_studio_user");
  updateUserUI();
  showToast("Signed out successfully.", "info");
  setStep(1);
}

/* ----------------------------------------------------
   3. JOB ROLES & PREFERENCES (STEP 2)
---------------------------------------------------- */
function renderPresetChips() {
  const chips = document.querySelectorAll(".role-chip");
  chips.forEach(chip => {
    const roleName = chip.dataset.role;
    if (state.selectedRoles.includes(roleName)) {
      chip.classList.add("active");
      chip.querySelector(".chip-check").innerText = "✓";
    } else {
      chip.classList.remove("active");
      chip.querySelector(".chip-check").innerText = "+";
    }
  });
}

function renderSelectedRolesPills() {
  const container = document.getElementById("selected-roles-pills");
  const countEl = document.getElementById("selected-roles-count");
  if (!container) return;

  countEl.innerText = state.selectedRoles.length;
  container.innerHTML = "";

  if (state.selectedRoles.length === 0) {
    container.innerHTML = `<span class="text-muted" style="font-size: 13px;">No roles selected yet. Click chips above or add custom role tags.</span>`;
    return;
  }

  state.selectedRoles.forEach(role => {
    const pill = document.createElement("div");
    pill.className = "selected-role-pill";
    pill.innerHTML = `
      <span>🎯 ${escapeHtml(role)}</span>
      <button class="remove-pill-btn" data-role="${escapeHtml(role)}">&times;</button>
    `;
    pill.querySelector(".remove-pill-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      toggleRoleSelection(role);
    });
    container.appendChild(pill);
  });
}

function toggleRoleSelection(roleName) {
  if (roleName === "All Roles") {
    if (state.selectedRoles.includes("All Roles")) {
      state.selectedRoles = ["Machine Learning Engineer", "Data Scientist", "Software Engineer"];
    } else {
      state.selectedRoles = ["All Roles"];
    }
  } else {
    // If specific role clicked, clear All Roles if present
    state.selectedRoles = state.selectedRoles.filter(r => r !== "All Roles");
    if (state.selectedRoles.includes(roleName)) {
      state.selectedRoles = state.selectedRoles.filter(r => r !== roleName);
    } else {
      state.selectedRoles.push(roleName);
    }
  }
  renderPresetChips();
  renderSelectedRolesPills();
}

function addCustomRole(roleName) {
  const trimmed = roleName.trim();
  if (!trimmed) return;
  if (!state.selectedRoles.includes(trimmed)) {
    state.selectedRoles.push(trimmed);
    showToast(`Added role tag: "${trimmed}"`, "success");
    renderPresetChips();
    renderSelectedRolesPills();
  } else {
    showToast("Role is already in your selected list.", "info");
  }
}

/* ----------------------------------------------------
   4. JOB SEARCH & RESULTS (STEP 3)
---------------------------------------------------- */
async function performJobSearch() {
  const gridContainer = document.getElementById("jobs-cards-grid");
  gridContainer.innerHTML = `
    <div class="loading-state glass-card">
      <div class="spinner-ring"></div>
      <p>Searching top tech platforms for <strong>${state.selectedRoles.slice(0, 3).join(", ")}</strong>...</p>
    </div>
  `;

  // Get selected locations
  const locCheckboxes = document.querySelectorAll("#location-tags-container input:checked");
  state.selectedLocations = Array.from(locCheckboxes).map(cb => cb.value);

  // Get enabled platforms
  state.enabledPlatforms = {
    linkedin: document.getElementById("plat-linkedin")?.checked ?? true,
    naukri: document.getElementById("plat-naukri")?.checked ?? true,
    glassdoor: document.getElementById("plat-glassdoor")?.checked ?? true
  };

  try {
    const res = await fetch(`${API_BASE}/api/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target_roles: state.selectedRoles,
        locations: state.selectedLocations,
        enabled_platforms: state.enabledPlatforms
      })
    });

    const data = await res.json();
    state.jobs = data.jobs || [];

    // Update KPI strip
    document.getElementById("kpi-search-count").innerText = state.jobs.length;
    document.getElementById("kpi-active-roles-count").innerText = state.selectedRoles.length;
    document.getElementById("kpi-saved-jobs-count").innerText = state.savedJobs.length;

    // Populate role filter dropdown
    populateRoleDropdownFilter();

    // Render Grid Cards
    renderJobsGrid(state.jobs);

  } catch(err) {
    console.error("Search failed:", err);
    gridContainer.innerHTML = `
      <div class="glass-card" style="padding: 40px; text-align: center; color: var(--accent-rose);">
        <p>⚠️ Failed to load job search results. Please make sure server.py is running.</p>
      </div>
    `;
  }
}

function renderJobsGrid(jobsList) {
  const gridContainer = document.getElementById("jobs-cards-grid");
  gridContainer.innerHTML = "";

  if (jobsList.length === 0) {
    gridContainer.innerHTML = `
      <div class="glass-card" style="grid-column: 1/-1; padding: 48px; text-align: center;">
        <p style="font-size: 18px; font-weight: 700;">No matching job postings found.</p>
        <p style="font-size: 13px; color: var(--text-muted); margin-top: 6px;">Try adjusting your search keywords or adding more target job roles in Step 2.</p>
      </div>
    `;
    return;
  }

  jobsList.forEach(job => {
    const isSaved = state.savedJobs.some(s => s.url === job.url || s.job_id === job.job_id);
    const sourceClass = (job.source || "LinkedIn").toLowerCase();
    
    // Calculate simulated match score based on target roles
    let matchScore = 92;
    if (job.title && state.selectedRoles.some(r => job.title.toLowerCase().includes(r.toLowerCase()))) {
      matchScore = 98;
    }

    const card = document.createElement("div");
    card.className = "job-card";
    card.innerHTML = `
      <div>
        <div class="job-card-header">
          <div class="company-brand-box">
            <div class="company-logo-circle">${(job.company || "C")[0].toUpperCase()}</div>
            <div class="job-title-group">
              <h3>${escapeHtml(job.title)}</h3>
              <div class="company-name">${escapeHtml(job.company || "Unknown Company")}</div>
            </div>
          </div>
          <span class="match-badge">${matchScore}% Match</span>
        </div>

        <div class="job-card-meta">
          <span class="meta-pill platform-pill ${sourceClass}">${escapeHtml(job.source || "Web")}</span>
          <span class="meta-pill">📍 ${escapeHtml(job.location || "Remote")}</span>
          <span class="meta-pill">🕒 ${escapeHtml(job.posted_text || "Recent")}</span>
        </div>

        <p class="job-snippet">${escapeHtml(job.description_snippet || "No detailed description snippet provided.")}</p>
      </div>

      <div class="job-card-footer">
        <button class="btn-bookmark ${isSaved ? 'saved' : ''}" data-job-id="${escapeHtml(job.job_id)}">
          <span>${isSaved ? '★ Bookmarked' : '☆ Save Job'}</span>
        </button>

        <a href="${escapeHtml(job.url || '#')}" target="_blank" class="btn-apply-link">
          <span>Apply Direct</span>
          <span>↗</span>
        </a>
      </div>
    `;

    // Bookmark Toggle Event
    card.querySelector(".btn-bookmark").addEventListener("click", () => {
      toggleSaveJob(job);
    });

    gridContainer.appendChild(card);
  });
}

function filterJobsLocal() {
  const query = document.getElementById("jobs-search-query").value.toLowerCase().trim();
  const roleFilter = document.getElementById("select-role-filter").value;
  const platformFilter = document.getElementById("select-platform-filter").value;

  let filtered = state.jobs.filter(job => {
    const matchesQuery = !query || 
      (job.title && job.title.toLowerCase().includes(query)) ||
      (job.company && job.company.toLowerCase().includes(query)) ||
      (job.location && job.location.toLowerCase().includes(query)) ||
      (job.description_snippet && job.description_snippet.toLowerCase().includes(query));

    const matchesRole = (roleFilter === "all") || (job.title && job.title.toLowerCase().includes(roleFilter.toLowerCase()));
    const matchesPlatform = (platformFilter === "all") || (job.source && job.source.toLowerCase() === platformFilter.toLowerCase());

    return matchesQuery && matchesRole && matchesPlatform;
  });

  renderJobsGrid(filtered);
}

function populateRoleDropdownFilter() {
  const select = document.getElementById("select-role-filter");
  if (!select) return;

  select.innerHTML = `<option value="all">All Selected Roles</option>`;
  state.selectedRoles.forEach(role => {
    const opt = document.createElement("option");
    opt.value = role;
    opt.innerText = role;
    select.appendChild(opt);
  });
}

async function toggleSaveJob(job) {
  try {
    const res = await fetch(`${API_BASE}/api/jobs/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job })
    });
    const data = await res.json();
    if (data.status === "success") {
      state.savedJobs = data.saved_jobs || [];
      document.getElementById("kpi-saved-jobs-count").innerText = state.savedJobs.length;
      showToast(`Saved "${job.title}" to application tracker!`, "success");
      filterJobsLocal();
    }
  } catch(e) {
    showToast("Failed to save job bookmark.", "error");
  }
}

/* ----------------------------------------------------
   5. EMAIL DISPATCH & PREVIEW (STEP 4)
---------------------------------------------------- */
function initEmailStep() {
  const recipientInput = document.getElementById("recipient-email-input");
  if (recipientInput && state.currentUser) {
    recipientInput.value = state.currentUser.email;
  }
}

async function handleEmailDispatch(recipientEmail, subject, enableSMTP) {
  const btnSend = document.getElementById("btn-send-mail-now");
  btnSend.disabled = true;
  btnSend.innerHTML = `<span>⏳ Processing & Dispatching...</span>`;

  try {
    const res = await fetch(`${API_BASE}/api/send-email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recipient_email: recipientEmail,
        subject: subject,
        enable_smtp: enableSMTP
      })
    });

    const data = await res.json();
    state.lastEmailResult = data;

    // Display Email Dispatch Confirmation Card
    const resultCard = document.getElementById("email-result-card");
    resultCard.classList.remove("hidden");

    document.getElementById("res-recipient-email").innerText = data.recipient || recipientEmail;
    document.getElementById("res-jobs-count").innerText = `${data.job_count || state.jobs.length} postings`;
    document.getElementById("res-timestamp").innerText = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    document.getElementById("res-mode").innerText = data.send_digest_enabled ? "Sent via SMTP Server" : "Saved to Local HTML Preview";

    showToast("Job Digest Email dispatched successfully!", "success");

  } catch(err) {
    console.error("Email dispatch failed:", err);
    showToast("Failed to connect to backend email server.", "error");
  } finally {
    btnSend.disabled = false;
    btnSend.innerHTML = `<span class="btn-icon">🚀</span><span>Send Job Digest Email Now</span>`;
  }
}

/* ----------------------------------------------------
   6. EVENT LISTENERS SETUP
---------------------------------------------------- */
function setupEventListeners() {
  // Wizard Navigation Node Clicks (allow jumping back to completed steps)
  document.querySelectorAll(".wizard-step").forEach(stepNode => {
    stepNode.addEventListener("click", () => {
      const targetStep = parseInt(stepNode.dataset.step, 10);
      if (targetStep <= state.currentStep || state.currentUser) {
        setStep(targetStep);
      }
    });
  });

  // Prev Step Buttons
  document.querySelectorAll(".btn-prev-step").forEach(btn => {
    btn.addEventListener("click", () => {
      const target = parseInt(btn.dataset.target, 10);
      setStep(target);
    });
  });

  // Step 1: Login Form
  const loginForm = document.getElementById("login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const email = document.getElementById("login-email").value;
      const password = document.getElementById("login-password").value;
      handleLogin(email, password);
    });
  }

  // Step 1: Quick Demo Sign In
  const btnQuickLogin = document.getElementById("btn-quick-login");
  if (btnQuickLogin) {
    btnQuickLogin.addEventListener("click", () => {
      handleLogin("pavanateja@example.com", "demo1234");
    });
  }

  // Logout
  const btnLogout = document.getElementById("btn-logout");
  if (btnLogout) {
    btnLogout.addEventListener("click", handleLogout);
  }

  // Step 2: Preset Chips Clicking
  const presetGrid = document.getElementById("preset-roles-grid");
  if (presetGrid) {
    presetGrid.addEventListener("click", (e) => {
      const chip = e.target.closest(".role-chip");
      if (chip) {
        const role = chip.dataset.role;
        toggleRoleSelection(role);
      }
    });
  }

  // Step 2: Add Custom Role
  const btnAddCustom = document.getElementById("btn-add-custom-role");
  const customInput = document.getElementById("custom-role-input");
  if (btnAddCustom && customInput) {
    const triggerAdd = () => {
      addCustomRole(customInput.value);
      customInput.value = "";
    };
    btnAddCustom.addEventListener("click", triggerAdd);
    customInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        triggerAdd();
      }
    });
  }

  // Step 2: Save Roles & Search Action
  const btnSaveRoles = document.getElementById("btn-save-roles-and-search");
  if (btnSaveRoles) {
    btnSaveRoles.addEventListener("click", () => {
      if (state.selectedRoles.length === 0) {
        showToast("Please select at least one job role.", "warning");
        return;
      }
      setStep(3);
    });
  }

  // Step 3: Search & Filters
  const searchInput = document.getElementById("jobs-search-query");
  if (searchInput) searchInput.addEventListener("input", filterJobsLocal);

  const roleFilterSelect = document.getElementById("select-role-filter");
  if (roleFilterSelect) roleFilterSelect.addEventListener("change", filterJobsLocal);

  const platformFilterSelect = document.getElementById("select-platform-filter");
  if (platformFilterSelect) platformFilterSelect.addEventListener("change", filterJobsLocal);

  // Step 3: Proceed to Email
  const btnProceedEmail = document.getElementById("btn-proceed-to-email");
  const btnGotoStep4 = document.getElementById("btn-goto-step-4");
  if (btnProceedEmail) btnProceedEmail.addEventListener("click", () => setStep(4));
  if (btnGotoStep4) btnGotoStep4.addEventListener("click", () => setStep(4));

  // Step 3: Live Web Scraper Trigger
  const btnRunScraper = document.getElementById("btn-run-pipeline-fresh");
  if (btnRunScraper) {
    btnRunScraper.addEventListener("click", async () => {
      showToast("Triggering live scraper pipeline in background...", "info");
      try {
        await fetch(`${API_BASE}/api/run-pipeline`, { method: "POST" });
        showToast("Scraper task launched! Postings will refresh shortly.", "success");
      } catch(e) {
        showToast("Scraper request sent.", "info");
      }
    });
  }

  // Step 4: Email Form Submit
  const emailForm = document.getElementById("email-dispatch-form");
  if (emailForm) {
    emailForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const recipient = document.getElementById("recipient-email-input").value;
      const subject = document.getElementById("email-subject-input").value;
      const smtpToggle = document.getElementById("enable-smtp-toggle").checked;
      handleEmailDispatch(recipient, subject, smtpToggle);
    });
  }

  // Step 4: Preview Modal Triggers
  const btnOpenModal = document.getElementById("btn-open-preview-modal");
  const modalOverlay = document.getElementById("modal-email-preview");
  const btnCloseModal = document.getElementById("btn-close-modal");
  const btnModalDone = document.getElementById("btn-modal-done");

  if (btnOpenModal && modalOverlay) {
    btnOpenModal.addEventListener("click", () => {
      const iframe = document.getElementById("iframe-email-preview");
      if (iframe) iframe.src = `/api/digest-preview?t=${Date.now()}`;
      modalOverlay.classList.remove("hidden");
    });
  }

  if (btnCloseModal && modalOverlay) btnCloseModal.addEventListener("click", () => modalOverlay.classList.add("hidden"));
  if (btnModalDone && modalOverlay) btnModalDone.addEventListener("click", () => modalOverlay.classList.add("hidden"));

  // Restart Workflow
  const btnRestart = document.getElementById("btn-restart-workflow");
  if (btnRestart) {
    btnRestart.addEventListener("click", () => setStep(2));
  }
}

/* ----------------------------------------------------
   7. INITIAL CONFIG & UTILS
---------------------------------------------------- */
async function checkBackendStatus() {
  const pillText = document.getElementById("backend-status-text");
  try {
    const res = await fetch(`${API_BASE}/api/config`);
    if (res.ok) {
      pillText.innerText = "Backend Connected";
    }
  } catch(e) {
    pillText.innerText = "Backend Offline (Demo)";
  }
}

async function loadInitialConfig() {
  try {
    const res = await fetch(`${API_BASE}/api/config`);
    const cfg = await res.json();
    if (cfg.target_roles && cfg.target_roles.length > 0) {
      state.selectedRoles = cfg.target_roles;
    }
  } catch(e) {}
}

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = "toast";
  
  let icon = "ℹ️";
  if (type === "success") icon = "✅";
  if (type === "error") icon = "⚠️";
  if (type === "warning") icon = "🔔";

  toast.innerHTML = `<span>${icon}</span><span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
