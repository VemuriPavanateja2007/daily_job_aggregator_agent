// Content Script for web job page clipping
(function() {
  if (window.jobClipperInjected) return;
  window.jobClipperInjected = true;

  function createFloatingButton() {
    const btn = document.createElement("button");
    btn.id = "job-clipper-float-btn";
    btn.innerHTML = `<span>📌 Save to Job Alert</span>`;
    btn.style.cssText = `
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 999999;
      background: linear-gradient(135deg, #0284c7, #2563eb);
      color: #ffffff;
      border: none;
      padding: 10px 16px;
      border-radius: 30px;
      font-family: system-ui, -apple-system, sans-serif;
      font-size: 13px;
      font-weight: 700;
      box-shadow: 0 10px 25px -5px rgba(2, 132, 199, 0.5);
      cursor: pointer;
      transition: transform 0.2s, box-shadow 0.2s;
    `;

    btn.addEventListener("mouseover", () => {
      btn.style.transform = "scale(1.05)";
    });
    btn.addEventListener("mouseout", () => {
      btn.style.transform = "scale(1)";
    });

    btn.addEventListener("click", () => {
      btn.innerText = "⏳ Saving...";
      
      const jobData = {
        title: extractJobTitle(),
        company: extractCompanyName(),
        location: extractLocation(),
        url: window.location.href,
        source: getPlatformName(),
        status: "Saved",
        notes: `Clipped from ${getPlatformName()} on ${new Date().toLocaleDateString()}`
      };

      chrome.runtime.sendMessage({ action: "saveJob", job: jobData }, (response) => {
        if (response && response.success) {
          btn.innerHTML = `<span>✅ Saved to Dashboard!</span>`;
          btn.style.background = "#059669";
          setTimeout(() => {
            btn.innerHTML = `<span>📌 Save to Job Alert</span>`;
            btn.style.background = "linear-gradient(135deg, #0284c7, #2563eb)";
          }, 3000);
        } else {
          btn.innerHTML = `<span>❌ Save Failed</span>`;
          btn.style.background = "#dc2626";
          setTimeout(() => {
            btn.innerHTML = `<span>📌 Save to Job Alert</span>`;
            btn.style.background = "linear-gradient(135deg, #0284c7, #2563eb)";
          }, 3000);
        }
      });
    });

    document.body.appendChild(btn);
  }

  function extractJobTitle() {
    const h1 = document.querySelector("h1");
    if (h1 && h1.innerText.trim()) return h1.innerText.trim();
    return document.title.split("-")[0].trim();
  }

  function extractCompanyName() {
    const companyEl = document.querySelector(".job-details-jobs-unified-top-card__company-name, .companyName, [data-at='company-name']");
    if (companyEl) return companyEl.innerText.trim();
    if (document.title.includes("-")) return document.title.split("-")[1].trim();
    return "Company";
  }

  function extractLocation() {
    const locEl = document.querySelector(".job-details-jobs-unified-top-card__bullet, .location, [data-at='job-location']");
    if (locEl) return locEl.innerText.trim();
    return "Remote / Web";
  }

  function getPlatformName() {
    const host = window.location.hostname;
    if (host.includes("linkedin")) return "LinkedIn";
    if (host.includes("naukri")) return "Naukri";
    if (host.includes("glassdoor")) return "Glassdoor";
    if (host.includes("indeed")) return "Indeed";
    return "Web Page";
  }

  // Delay injection slightly to ensure body exists
  if (document.body) {
    createFloatingButton();
  } else {
    document.addEventListener("DOMContentLoaded", createFloatingButton);
  }
})();
