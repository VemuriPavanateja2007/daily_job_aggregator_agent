# 🚀 Daily Job Aggregator (`import antigravity`)

An automated, resilient Python job aggregator designed for AI/ML and Data Science job seekers. Fetches job postings from **LinkedIn**, **Naukri**, **Glassdoor**, and optional API aggregators, filters for fresh postings (<24h), deduplicates cross-posted listings, and dispatches a clean, responsive HTML email digest to your inbox.

---

## 🏗️ System Architecture

```text
                                 ┌───────────────────────┐
                                 │      config.yaml      │
                                 └───────────┬───────────┘
                                             │
                                 ┌───────────▼───────────┐
                                 │     main.py (Async)   │
                                 └───────────┬───────────┘
                                             │
      ┌──────────────────────────────┬───────┴───────────────┬──────────────────────────────┐
      │                              │                       │                              │
┌─────▼───────────────┐   ┌──────────▼──────────┐  ┌─────────▼───────────┐   ┌─────────────▼─────────────┐
│ LinkedInFetcher     │   │ NaukriFetcher       │  │ GlassdoorFetcher    │   │ RapidAPIFetcher (Backup)  │
│ (Playwright Stealth)│   │ (Playwright Stealth)│  │ (Cloudflare Shield) │   │ (JSearch API)             │
└─────┬───────────────┘   └──────────┬──────────┘  └─────────┬───────────┘   └─────────────┬─────────────┘
      │                              │                       │                             │
      └──────────────────────────────┴───────┬───────────────┴─────────────────────────────┘
                                             │ (JobPosting Objects)
                                 ┌───────────▼───────────┐
                                 │     DataProcessor     │
                                 │   (Pandas & Pydantic) │
                                 └───────────┬───────────┘
                                             │ (Clean 24h & Deduped Jobs)
                                 ┌───────────▼───────────┐
                                 │     EmailNotifier     │
                                 │     (Jinja2 + SMTP)   │
                                 └───────────┬───────────┘
                                             │
                                 ┌───────────▼───────────┐
                                 │  📥 Inbox HTML Digest │
                                 └───────────────────────┘
```

---

## ✨ Features

- **Modular & OOP Design**: Abstract base class (`BaseFetcher`) allowing seamless addition of new job sources.
- **Stealth Headless Scraping**: Powered by `playwright-stealth` with automated browser headers and non-automated context flags.
- **Fault-Tolerant Concurrency**: Built with `asyncio.gather(..., return_exceptions=True)`. If Glassdoor triggers Cloudflare checks, LinkedIn and Naukri continue unimpeded.
- **Strict 24-Hour Filter**: Parses dynamic age tags ("2 hours ago", "Yesterday", "Just posted") and keeps only fresh postings.
- **Multi-Field Deduplication**: Uses `Pandas` normalization (normalizes titles, corporate suffixes, company names, and canonical URLs) to remove cross-posted duplicates.
- **Responsive Jinja2 HTML Digest**: Formatted HTML layout with direct application deep-links and platform badge highlights.

---

## ⚡ Quick Start & Installation

### 1. Prerequisites
Ensure Python 3.9+ is installed on your system.

### 2. Install Dependencies
Navigate to the project root and install the required Python packages:

```bash
pip install -r requirements.txt
playwright install chromium
```

---

## ⚙️ Configuration (`config.yaml`)

Edit `config.yaml` to customize target roles, locations, and email credentials:

```yaml
target_roles:
  - "Machine Learning Engineer"
  - "Data Scientist"

locations:
  - "Remote"
  - "India"

max_age_hours: 24

enabled_platforms:
  linkedin: true
  naukri: true
  glassdoor: true
  rapidapi: false

email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  sender_email: "your_email@gmail.com"
  sender_password: "YOUR_GMAIL_APP_PASSWORD" # Create an App Password in your Google Account
  recipient_email: "your_email@gmail.com"
  send_digest: true
```

> 🔑 **Gmail App Password Instructions**:
> 1. Go to your Google Account -> **Security**.
> 2. Enable **2-Step Verification**.
> 3. Search for **App Passwords**, generate a key for "Mail", and paste the 16-character string into `sender_password`.

---

## 🚀 Running the Script

### Dry-Run Mode (Test without sending emails)
Executes scrapers, processes data, and outputs an interactive HTML preview to `digest_preview.html`:

```bash
python main.py --dry-run
```

### Full Production Run
Fetches jobs and dispatches the HTML email digest to your inbox:

```bash
python main.py --config config.yaml
```

---

## 📅 Scheduling Daily Automation

### Windows Task Scheduler
To run this script automatically every day at 8:00 AM:

1. Open **Task Scheduler** -> **Create Basic Task**.
2. Trigger: **Daily** at 8:00 AM.
3. Action: **Start a program**.
4. Program/script: `python` (or path to your `python.exe`).
5. Add arguments: `main.py`
6. Start in: `C:\Users\V V S H PAVANATEJA\.gemini\antigravity-ide\scratch\daily_job_aggregator`

