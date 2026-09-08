import asyncio
import json
import logging
import sys
import os
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, List
from urllib.parse import parse_qs, urlparse

try:
    import yaml
except ImportError:
    yaml = None

from core.models import AggregatorConfig, JobPosting
from core.notifier import EmailNotifier
from core.processor import DataProcessor

logger = logging.getLogger("JobAggregator.Server")
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
CONFIG_PATH = BASE_DIR / "config.yaml"

DATA_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

JOBS_FILE = DATA_DIR / "jobs.json"
SAVED_JOBS_FILE = DATA_DIR / "saved_jobs.json"
HISTORY_FILE = DATA_DIR / "history.json"


def load_config_raw() -> Dict[str, Any]:
    default_cfg = {
        "target_roles": ["Machine Learning Engineer", "Data Scientist", "Software Engineer"],
        "locations": ["Remote", "India"],
        "max_age_hours": 24.0,
        "enabled_platforms": {"linkedin": True, "naukri": True, "glassdoor": True, "rapidapi": False},
        "browser_settings": {"headless": True, "timeout_ms": 30000},
        "email": {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "sender_email": "demo@example.com",
            "sender_password": "",
            "recipient_email": "demo@example.com",
            "send_digest": False
        }
    }
    if not CONFIG_PATH.exists():
        return default_cfg

    if yaml is None:
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                content = f.read()
                roles = []
                for line in content.splitlines():
                    if line.strip().startswith("- "):
                        role = line.strip()[2:].strip('"\'')
                        if role and role not in roles:
                            roles.append(role)
                if roles:
                    default_cfg["target_roles"] = roles
                return default_cfg
        except Exception:
            return default_cfg

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                # Deep merge email dictionary so sender credentials are never lost
                if "email" in loaded and isinstance(loaded["email"], dict):
                    merged_email = default_cfg["email"].copy()
                    merged_email.update(loaded["email"])
                    loaded["email"] = merged_email
                return loaded
            return default_cfg
    except Exception as e:
        logger.error(f"Failed to parse config.yaml: {e}")
        return default_cfg


def save_config_raw(data: Dict[str, Any]) -> None:
    if yaml is not None:
        try:
            current = load_config_raw()
            if isinstance(data, dict):
                for k, v in data.items():
                    if k == "email" and isinstance(v, dict) and isinstance(current.get("email"), dict):
                        current["email"].update(v)
                    else:
                        current[k] = v
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.safe_dump(current, f, sort_keys=False, default_flow_style=False)
        except Exception as e:
            logger.error(f"Failed to save config.yaml: {e}")




def load_json_file(file_path: Path, default_val: Any) -> Any:
    if not file_path.exists():
        return default_val
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        return default_val


def save_json_file(file_path: Path, data: Any) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# Initialize mock sample data if jobs.json is empty or doesn't exist
def ensure_sample_data():
    now_str = datetime.now(timezone.utc).isoformat()
    sample_jobs = [
        {
            "job_id": "job_sample_01",
            "title": "Senior Machine Learning Engineer",
            "company": "DeepTech Innovations",
            "location": "Remote",
            "url": "https://www.linkedin.com/jobs/view/1001",
            "source": "LinkedIn",
            "posted_text": "2 hours ago",
            "posted_hours_ago": 2.0,
            "is_sponsored": False,
            "description_snippet": "Building enterprise LLM pipelines, PyTorch models, and computer vision microservices.",
            "scraped_at": now_str
        },
        {
            "job_id": "job_sample_02",
            "title": "Data Scientist - Generative AI",
            "company": "AnalyticsCorp Labs",
            "location": "Bangalore, India",
            "url": "https://www.naukri.com/job-listings-1002",
            "source": "Naukri",
            "posted_text": "4 hours ago",
            "posted_hours_ago": 4.0,
            "is_sponsored": True,
            "description_snippet": "Looking for Data Scientists skilled in Python, Scikit-learn, LangChain, and RAG architectures.",
            "scraped_at": now_str
        },
        {
            "job_id": "job_sample_03",
            "title": "Full Stack AI Engineer",
            "company": "NextGen Systems",
            "location": "Remote",
            "url": "https://www.glassdoor.com/job-listing/1003",
            "source": "Glassdoor",
            "posted_text": "5 hours ago",
            "posted_hours_ago": 5.0,
            "is_sponsored": False,
            "description_snippet": "Develop modern React interfaces and Python FastAPI microservices for web applications.",
            "scraped_at": now_str
        },
        {
            "job_id": "job_sample_04",
            "title": "Python Backend & AI Developer",
            "company": "CloudNimbus Solutions",
            "location": "Hyderabad, India",
            "url": "https://www.linkedin.com/jobs/view/1004",
            "source": "LinkedIn",
            "posted_text": "1 hour ago",
            "posted_hours_ago": 1.0,
            "is_sponsored": False,
            "description_snippet": "Designing scalable REST/gRPC endpoints, Docker containers, PostgreSQL, and Redis caching.",
            "scraped_at": now_str
        },
        {
            "job_id": "job_sample_05",
            "title": "Lead Machine Learning Researcher",
            "company": "Apex AI Research",
            "location": "Remote",
            "url": "https://www.glassdoor.com/job-listing/1005",
            "source": "Glassdoor",
            "posted_text": "6 hours ago",
            "posted_hours_ago": 6.0,
            "is_sponsored": False,
            "description_snippet": "Leading fine-tuning of open-source LLMs (Llama 3, Mistral) and model evaluation metrics.",
            "scraped_at": now_str
        },
        {
            "job_id": "job_sample_06",
            "title": "Senior Software Engineer - Distributed Systems",
            "company": "Global Scale Systems",
            "location": "Remote",
            "url": "https://www.linkedin.com/jobs/view/1006",
            "source": "LinkedIn",
            "posted_text": "3 hours ago",
            "posted_hours_ago": 3.0,
            "is_sponsored": False,
            "description_snippet": "Architecting high-throughput distributed microservices in Go, Java, and Kubernetes.",
            "scraped_at": now_str
        },
        {
            "job_id": "job_sample_07",
            "title": "Frontend React & Next.js Developer",
            "company": "PixelCraft Studios",
            "location": "Bangalore, India",
            "url": "https://www.naukri.com/job-listings-1007",
            "source": "Naukri",
            "posted_text": "2 hours ago",
            "posted_hours_ago": 2.0,
            "is_sponsored": False,
            "description_snippet": "Crafting pixel-perfect dark-mode dashboards with React 18, TypeScript, Tailwind, and WebGL.",
            "scraped_at": now_str
        },
        {
            "job_id": "job_sample_08",
            "title": "DevOps & Site Reliability Engineer (SRE)",
            "company": "CloudScale Networks",
            "location": "Remote",
            "url": "https://www.glassdoor.com/job-listing/1008",
            "source": "Glassdoor",
            "posted_text": "4 hours ago",
            "posted_hours_ago": 4.0,
            "is_sponsored": True,
            "description_snippet": "Managing CI/CD pipelines, Terraform infra, Kubernetes clusters, and Prometheus monitoring.",
            "scraped_at": now_str
        },
        {
            "job_id": "job_sample_09",
            "title": "Data Engineer - Big Data & Snowflake",
            "company": "DataPipeline Pro",
            "location": "Mumbai, India",
            "url": "https://www.linkedin.com/jobs/view/1009",
            "source": "LinkedIn",
            "posted_text": "5 hours ago",
            "posted_hours_ago": 5.0,
            "is_sponsored": False,
            "description_snippet": "Building ETL pipelines with Apache Spark, PySpark, Airflow, and Snowflake data warehouses.",
            "scraped_at": now_str
        },
        {
            "job_id": "job_sample_10",
            "title": "Cloud Solutions Architect - AWS / Azure",
            "company": "Enterprise Infra Corp",
            "location": "Remote",
            "url": "https://www.naukri.com/job-listings-1010",
            "source": "Naukri",
            "posted_text": "1 hour ago",
            "posted_hours_ago": 1.0,
            "is_sponsored": False,
            "description_snippet": "Designing zero-trust cloud architectures, serverless Lambda systems, and multi-region deployment.",
            "scraped_at": now_str
        },
        {
            "job_id": "job_sample_11",
            "title": "Cybersecurity & Lead Pen Tester",
            "company": "SecureShield Tech",
            "location": "Delhi NCR, India",
            "url": "https://www.glassdoor.com/job-listing/1011",
            "source": "Glassdoor",
            "posted_text": "7 hours ago",
            "posted_hours_ago": 7.0,
            "is_sponsored": False,
            "description_snippet": "Performing application vulnerability assessments, threat modeling, and SOC compliance audits.",
            "scraped_at": now_str
        },
        {
            "job_id": "job_sample_12",
            "title": "Senior Product Manager - AI & Platform",
            "company": "VentureScale Inc",
            "location": "Remote",
            "url": "https://www.linkedin.com/jobs/view/1012",
            "source": "LinkedIn",
            "posted_text": "3 hours ago",
            "posted_hours_ago": 3.0,
            "is_sponsored": True,
            "description_snippet": "Driving AI product roadmaps, user growth experiments, feature prioritization, and metrics.",
            "scraped_at": now_str
        },
        {
            "job_id": "job_sample_13",
            "title": "Mobile App Developer - Flutter & React Native",
            "company": "AppSphere Studio",
            "location": "Remote",
            "url": "https://www.naukri.com/job-listings-1013",
            "source": "Naukri",
            "posted_text": "4 hours ago",
            "posted_hours_ago": 4.0,
            "is_sponsored": False,
            "description_snippet": "Building cross-platform iOS & Android apps with smooth animations, state management, and Firebase.",
            "scraped_at": now_str
        },
        {
            "job_id": "job_sample_14",
            "title": "AI Prompt Engineer & LLM Specialist",
            "company": "Cognitive AI Labs",
            "location": "Remote",
            "url": "https://www.glassdoor.com/job-listing/1014",
            "source": "Glassdoor",
            "posted_text": "2 hours ago",
            "posted_hours_ago": 2.0,
            "is_sponsored": False,
            "description_snippet": "Designing prompt engineering workflows, agentic chains, semantic search, and vector databases.",
            "scraped_at": now_str
        },
        {
            "job_id": "job_sample_15",
            "title": "QA Automation Engineer - Cypress & PyTest",
            "company": "QualityStack Solutions",
            "location": "Pune, India",
            "url": "https://www.linkedin.com/jobs/view/1015",
            "source": "LinkedIn",
            "posted_text": "6 hours ago",
            "posted_hours_ago": 6.0,
            "is_sponsored": False,
            "description_snippet": "Writing automated E2E test suites with Cypress, Playwright, Selenium, and GitHub Actions CI.",
            "scraped_at": now_str
        }
    ]
    save_json_file(JOBS_FILE, sample_jobs)

    if not SAVED_JOBS_FILE.exists():
        sample_saved = [
            {
                "job_id": "job_sample_01",
                "title": "Senior Machine Learning Engineer",
                "company": "DeepTech Innovations",
                "location": "Remote",
                "url": "https://www.linkedin.com/jobs/view/1001",
                "source": "LinkedIn",
                "status": "Applied",
                "notes": "Applied via LinkedIn Easy Apply on Monday.",
                "saved_at": now_str
            }
        ]
        save_json_file(SAVED_JOBS_FILE, sample_saved)

    if not HISTORY_FILE.exists():
        sample_history = [
            {
                "id": "digest_01",
                "timestamp": now_str,
                "job_count": len(sample_jobs),
                "recipient": "user@example.com",
                "status": "Success (Local Preview)"
            }
        ]
        save_json_file(HISTORY_FILE, sample_history)


class AggregatorRequestHandler(BaseHTTPRequestHandler):
    """CORS-enabled REST API and static asset handler."""

    def _set_headers(self, status_code: int = 200, content_type: str = "application/json"):
        self.send_response(status_code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, PATCH")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Content-Type", content_type)
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def _send_json(self, data: Any, status_code: int = 200):
        self._set_headers(status_code, "application/json")
        self.wfile.write(json.dumps(data, default=str).encode("utf-8"))

    def _send_error(self, message: str, status_code: int = 400):
        self._send_json({"error": message}, status_code)

    def _read_body_json(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        raw_body = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(raw_body)
        except Exception:
            return {}

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)

        # API Endpoints
        if path == "/api/config":
            cfg = load_config_raw()
            self._send_json(cfg)
            return

        elif path == "/api/jobs":
            jobs = load_json_file(JOBS_FILE, [])
            role_filter = query.get("role", [None])[0]
            platform_filter = query.get("platform", [None])[0]
            search_query = query.get("q", [None])[0]

            filtered = jobs
            if role_filter and role_filter != "all":
                filtered = [j for j in filtered if role_filter.lower() in j.get("title", "").lower()]
            if platform_filter and platform_filter != "all":
                filtered = [j for j in filtered if j.get("source", "").lower() == platform_filter.lower()]
            if search_query:
                sq = search_query.lower()
                filtered = [
                    j for j in filtered
                    if sq in j.get("title", "").lower()
                    or sq in j.get("company", "").lower()
                    or sq in j.get("location", "").lower()
                    or sq in j.get("description_snippet", "").lower()
                ]
            self._send_json({"jobs": filtered, "total": len(filtered)})
            return

        elif path == "/api/saved-jobs":
            saved = load_json_file(SAVED_JOBS_FILE, [])
            self._send_json({"saved_jobs": saved, "total": len(saved)})
            return

        elif path == "/api/stats":
            jobs = load_json_file(JOBS_FILE, [])
            saved = load_json_file(SAVED_JOBS_FILE, [])
            cfg = load_config_raw()
            history = load_json_file(HISTORY_FILE, [])

            platforms_count = {}
            roles_count = {}
            for j in jobs:
                src = j.get("source", "Other")
                platforms_count[src] = platforms_count.get(src, 0) + 1
                title = j.get("title", "Other")
                roles_count[title] = roles_count.get(title, 0) + 1

            stats = {
                "total_jobs": len(jobs),
                "saved_count": len(saved),
                "active_roles": cfg.get("target_roles", []),
                "locations": cfg.get("locations", []),
                "platforms_breakdown": platforms_count,
                "roles_breakdown": roles_count,
                "last_digest_time": history[-1]["timestamp"] if history else "Never",
                "email_enabled": cfg.get("email", {}).get("send_digest", False),
                "recipient_email": cfg.get("email", {}).get("recipient_email", "")
            }
            self._send_json(stats)
            return

        elif path == "/api/history":
            history = load_json_file(HISTORY_FILE, [])
            self._send_json({"history": history})
            return

        elif path == "/api/digest-preview":
            preview_path = BASE_DIR / "digest_preview.html"
            if preview_path.exists():
                content = preview_path.read_text(encoding="utf-8")
                self._set_headers(200, "text/html")
                self.wfile.write(content.encode("utf-8"))
            else:
                self._send_error("No preview generated yet", 404)
            return

        # Serve static files for Web Dashboard
        if path == "/":
            path = "/index.html"

        file_path = STATIC_DIR / path.lstrip("/")
        if file_path.exists() and file_path.is_file():
            mime_type = "text/html"
            if file_path.suffix == ".css":
                mime_type = "text/css"
            elif file_path.suffix == ".js":
                mime_type = "application/javascript"
            elif file_path.suffix == ".json":
                mime_type = "application/json"
            elif file_path.suffix in [".png", ".jpg", ".jpeg"]:
                mime_type = f"image/{file_path.suffix.lstrip('.')}"
            elif file_path.suffix == ".svg":
                mime_type = "image/svg+xml"

            self._set_headers(200, mime_type)
            with open(file_path, "rb") as f:
                self.wfile.write(f.read())
            return

        self._send_error("File not found", 404)

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        body = self._read_body_json()

        if path == "/api/config":
            current = load_config_raw()
            if "target_roles" in body:
                current["target_roles"] = [r.strip() for r in body["target_roles"] if r.strip()]
            if "locations" in body:
                current["locations"] = [l.strip() for l in body["locations"] if l.strip()]
            if "max_age_hours" in body:
                current["max_age_hours"] = float(body["max_age_hours"])
            if "enabled_platforms" in body:
                current["enabled_platforms"].update(body["enabled_platforms"])
            if "email" in body:
                current["email"].update(body["email"])

            save_config_raw(current)
            self._send_json({"status": "success", "config": current})
            return

        elif path == "/api/roles/add":
            role_name = body.get("role", "").strip()
            if not role_name:
                self._send_error("Role name is required")
                return
            current = load_config_raw()
            roles = current.get("target_roles", [])
            if role_name not in roles:
                roles.append(role_name)
                current["target_roles"] = roles
                save_config_raw(current)
            self._send_json({"status": "success", "target_roles": current["target_roles"]})
            return

        elif path == "/api/roles/remove":
            role_name = body.get("role", "").strip()
            current = load_config_raw()
            roles = current.get("target_roles", [])
            if role_name in roles:
                roles.remove(role_name)
                current["target_roles"] = roles
                save_config_raw(current)
            self._send_json({"status": "success", "target_roles": current["target_roles"]})
            return

        elif path == "/api/jobs/save":
            job = body.get("job", {})
            if not job or not job.get("title"):
                self._send_error("Job data is invalid")
                return

            saved = load_json_file(SAVED_JOBS_FILE, [])
            job_id = job.get("job_id") or f"saved_{int(datetime.now().timestamp())}"
            existing = next((item for item in saved if item.get("url") == job.get("url") or item.get("job_id") == job_id), None)
            
            if existing:
                existing["status"] = job.get("status", existing.get("status", "Saved"))
                existing["notes"] = job.get("notes", existing.get("notes", ""))
            else:
                new_item = {
                    "job_id": job_id,
                    "title": job.get("title"),
                    "company": job.get("company", "Unknown"),
                    "location": job.get("location", "Remote"),
                    "url": job.get("url", "#"),
                    "source": job.get("source", "Clipped"),
                    "status": job.get("status", "Saved"),
                    "notes": job.get("notes", ""),
                    "saved_at": datetime.now(timezone.utc).isoformat()
                }
                saved.append(new_item)

            save_json_file(SAVED_JOBS_FILE, saved)
            self._send_json({"status": "success", "saved_jobs": saved})
            return

        elif path == "/api/jobs/update-status":
            job_id = body.get("job_id")
            new_status = body.get("status")
            notes = body.get("notes")

            saved = load_json_file(SAVED_JOBS_FILE, [])
            found = False
            for item in saved:
                if item.get("job_id") == job_id:
                    if new_status:
                        item["status"] = new_status
                    if notes is not None:
                        item["notes"] = notes
                    found = True
                    break

            if found:
                save_json_file(SAVED_JOBS_FILE, saved)
                self._send_json({"status": "success", "saved_jobs": saved})
            else:
                self._send_error("Saved job not found", 404)
            return

        elif path == "/api/login":
            email = body.get("email") or body.get("username", "user@example.com")
            password = body.get("password", "")
            # Simple demo auth response
            user_info = {
                "status": "success",
                "user": {
                    "email": email,
                    "name": email.split("@")[0].capitalize() if "@" in email else email,
                    "token": f"token_{int(datetime.now().timestamp())}"
                }
            }
            # Save recipient email in config as default
            current = load_config_raw()
            if "email" not in current:
                current["email"] = {}
            current["email"]["recipient_email"] = email
            save_config_raw(current)
            self._send_json(user_info)
            return

        elif path == "/api/search":
            current = load_config_raw()
            roles = body.get("target_roles", [])
            locations = body.get("locations", [])
            platforms = body.get("enabled_platforms", {})

            if roles:
                current["target_roles"] = [r.strip() for r in roles if r.strip()]
            if locations:
                current["locations"] = [l.strip() for l in locations if l.strip()]
            if platforms:
                current["enabled_platforms"].update(platforms)

            save_config_raw(current)

            all_jobs = load_json_file(JOBS_FILE, [])
            selected_roles = current.get("target_roles", [])

            # Check if "All Roles" or "All" is selected
            has_all = any(r.lower() in ["all", "all roles", "all tech roles", "select all"] for r in selected_roles)

            if not selected_roles or has_all:
                filtered = all_jobs
            else:
                # Flexible tokenized matching
                filtered = []
                for j in all_jobs:
                    title_lower = j.get("title", "").lower()
                    desc_lower = j.get("description_snippet", "").lower()
                    
                    matched = False
                    for r in selected_roles:
                        r_lower = r.lower()
                        # Direct substring match
                        if r_lower in title_lower or r_lower in desc_lower:
                            matched = True
                            break
                        # Tokenized keyword match (e.g. "Python Developer" matches "Python Backend")
                        tokens = [t for t in r_lower.split() if len(t) > 2 and t not in ["engineer", "developer", "senior", "lead"]]
                        if any(tok in title_lower or tok in desc_lower for tok in tokens):
                            matched = True
                            break

                    if matched:
                        filtered.append(j)

                # Fallback to all jobs if no specific match found to prevent empty screens
                if not filtered:
                    filtered = all_jobs

            self._send_json({
                "status": "success",
                "jobs": filtered,
                "total": len(filtered),
                "target_roles": current.get("target_roles", [])
            })
            return

        elif path in ["/api/send-test-email", "/api/send-email"]:
            cfg_dict = load_config_raw()
            recipient = body.get("recipient_email") or body.get("email")
            if "email" not in cfg_dict or not isinstance(cfg_dict["email"], dict):
                cfg_dict["email"] = {}

            if recipient:
                cfg_dict["email"]["recipient_email"] = recipient
            
            # Enable SMTP dispatch if requested or if credentials exist in config
            if body.get("enable_smtp") is not None:
                cfg_dict["email"]["send_digest"] = bool(body.get("enable_smtp"))
            elif cfg_dict["email"].get("sender_email") and cfg_dict["email"].get("sender_password"):
                cfg_dict["email"]["send_digest"] = True

            save_config_raw(cfg_dict)

            jobs_raw = load_json_file(JOBS_FILE, [])
            target_roles = cfg_dict.get("target_roles", [])
            if target_roles:
                matching_jobs = [
                    j for j in jobs_raw
                    if any(r.lower() in j.get("title", "").lower() or r.lower() in j.get("description_snippet", "").lower() for r in target_roles)
                ]
                if matching_jobs:
                    jobs_raw = matching_jobs

            job_models = [JobPosting(**j) for j in jobs_raw]

            notifier = EmailNotifier(
                config=AggregatorConfig(**cfg_dict).email,
                template_dir=BASE_DIR / "templates"
            )
            html_content = notifier.render_digest(job_models, cfg_dict.get("target_roles", []))
            target_recipient = cfg_dict.get("email", {}).get("recipient_email") or "user@example.com"
            subject = body.get("subject") or f"🚀 Daily Job Digest for {target_recipient}"
            
            success = notifier.send_email(html_content, subject=subject)
            is_smtp = success and cfg_dict.get("email", {}).get("send_digest", False)

            history = load_json_file(HISTORY_FILE, [])
            history_item = {
                "id": f"digest_{len(history)+1}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "job_count": len(job_models),
                "recipient": target_recipient,
                "status": "Dispatched via SMTP" if is_smtp else "Saved (Local HTML Preview)"
            }
            history.append(history_item)
            save_json_file(HISTORY_FILE, history)

            self._send_json({
                "status": "success" if is_smtp else "warning",
                "recipient": target_recipient,
                "job_count": len(job_models),
                "is_smtp": is_smtp,
                "preview_url": "/api/digest-preview",
                "message": f"Job Digest email dispatched to {target_recipient} via Gmail SMTP!" if is_smtp else f"Digest generated and saved to local preview for {target_recipient}.",
                "send_digest_enabled": cfg_dict.get("email", {}).get("send_digest", False),
                "history_entry": history_item
            })
            return

        elif path == "/api/run-pipeline":
            def run_in_bg():
                try:
                    from main import run_pipeline, load_config
                    cfg = load_config(CONFIG_PATH)
                    asyncio.run(run_pipeline(cfg, dry_run=False))
                    logger.info("Pipeline run complete.")
                except Exception as e:
                    logger.error(f"Error running pipeline: {e}")

            t = threading.Thread(target=run_in_bg, daemon=True)
            t.start()

            self._send_json({
                "status": "started",
                "message": "Job scraper pipeline initiated in background! Fresh postings will populate automatically."
            })
            return

        self._send_error("Invalid API endpoint", 404)


def run_server(port: int = 8000):
    ensure_sample_data()
    server_address = ("", port)
    httpd = HTTPServer(server_address, AggregatorRequestHandler)
    logger.info(f"🚀 Job Aggregator API & Web Dashboard running at http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down.")
        httpd.server_close()


# Vercel / WSGI / Serverless Entry Points
handler = AggregatorRequestHandler
app = AggregatorRequestHandler

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port)

