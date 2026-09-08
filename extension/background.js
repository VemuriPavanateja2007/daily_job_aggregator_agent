// Extension Service Worker (Manifest V3)
const API_BASE = "http://localhost:8000";

chrome.runtime.onInstalled.addListener(() => {
  console.log("🚀 Job Target & Alert Assistant Extension Installed!");
});

// Listener for messages from content scripts or popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "saveJob") {
    fetch(`${API_BASE}/api/jobs/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job: request.job })
    })
    .then(res => res.json())
    .then(data => sendResponse({ success: true, data }))
    .catch(err => sendResponse({ success: false, error: err.toString() }));
    return true; // Keep channel open for async response
  }
});
