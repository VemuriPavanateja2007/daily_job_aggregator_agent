import argparse
import asyncio
import logging
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import List
from urllib.parse import parse_qs, urlparse

try:
    import yaml
except ImportError:
    yaml = None

from core.models import AggregatorConfig, JobPosting
from core.notifier import EmailNotifier
from core.processor import DataProcessor
from scrapers.glassdoor_fetcher import GlassdoorFetcher
from scrapers.linkedin_fetcher import LinkedInFetcher
from scrapers.naukri_fetcher import NaukriFetcher
from scrapers.api_fetcher import RapidAPIFetcher


# Configure UTF-8 for console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Setup application logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("JobAggregator.Main")


def load_config(config_path: Path) -> AggregatorConfig:
    """Load and validate configuration from YAML/JSON file."""
    if not config_path.exists():
        logger.error(f"Configuration file not found at: {config_path}")
        sys.exit(1)

    if yaml is None:
        logger.error("PyYAML is not installed. Please run: pip install -r requirements.txt")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f)

    return AggregatorConfig(**raw_data)



async def run_pipeline(config: AggregatorConfig, dry_run: bool = False):
    """
    Main execution pipeline:
    1. Instantiate enabled scrapers
    2. Concurrently fetch jobs across target roles and locations
    3. Clean and deduplicate postings (24h filter)
    4. Render and dispatch HTML email digest
    """
    logger.info("Initializing Daily Job Aggregator pipeline...")

    scrapers = []
    if config.enabled_platforms.get("linkedin", True):
        scrapers.append(LinkedInFetcher(config.browser_settings))
    if config.enabled_platforms.get("naukri", True):
        scrapers.append(NaukriFetcher(config.browser_settings))
    if config.enabled_platforms.get("glassdoor", True):
        scrapers.append(GlassdoorFetcher(config.browser_settings))
    if config.enabled_platforms.get("rapidapi", False):
        scrapers.append(RapidAPIFetcher(config.browser_settings, config.rapidapi))

    if not scrapers:
        logger.warning("No fetchers are enabled in config.yaml! Exiting.")
        return

    # Build concurrent fetch tasks
    fetch_tasks = []
    for role in config.target_roles:
        for loc in config.locations:
            for scraper in scrapers:
                fetch_tasks.append(scraper.fetch_jobs(role, loc))

    logger.info(f"Launching {len(fetch_tasks)} concurrent scraping tasks via asyncio...")
    results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    # Flatten task outputs while filtering out exceptions
    raw_postings: List[JobPosting] = []
    for res in results:
        if isinstance(res, list):
            raw_postings.extend(res)
        elif isinstance(res, Exception):
            logger.error(f"Scraper task encountered unhandled exception: {res}")

    logger.info(f"Total raw postings collected: {len(raw_postings)}")

    # Step 3: Data Processing & Deduplication
    processor = DataProcessor(max_age_hours=config.max_age_hours)
    clean_postings = processor.process(raw_postings)

    # Step 4: Dispatch Email Digest
    templates_dir = Path(__file__).parent / "templates"
    notifier = EmailNotifier(config.email, templates_dir)

    html_digest = notifier.render_digest(clean_postings, config.target_roles)

    if dry_run:
        logger.info("[DRY RUN MODE] Email sending skipped. Preview saved to digest_preview.html.")
    else:
        notifier.send_email(html_digest)

    logger.info("✨ Pipeline completed successfully!")


class handler(BaseHTTPRequestHandler):
    """Vercel Serverless Function entry point."""

    def do_GET(self):
        try:
            parsed_path = urlparse(self.path)
            params = parse_qs(parsed_path.query)

            # Trigger pipeline run if requested via query or cron route
            if "run" in params or parsed_path.path in ["/run", "/api/cron"]:
                config_path = Path(__file__).parent / "config.yaml"
                if config_path.exists():
                    config = load_config(config_path)
                    dry_run = params.get("dry_run", ["true"])[0].lower() != "false"
                    asyncio.run(run_pipeline(config, dry_run=dry_run))

            preview_path = Path(__file__).parent / "digest_preview.html"
            if preview_path.exists():
                with open(preview_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(content.encode("utf-8"))
                return

            html_response = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Job Aggregator</title>
    <style>
        body { font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .card { background: #1e293b; border-radius: 12px; padding: 2.5rem; max-width: 520px; width: 90%; border: 1px solid #334155; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5); text-align: center; }
        h1 { color: #38bdf8; margin-top: 0; font-size: 1.8rem; }
        p { color: #94a3b8; line-height: 1.6; }
        .badge { background: #0284c7; color: #fff; padding: 4px 10px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; }
        .actions { margin-top: 1.5rem; display: flex; gap: 10px; justify-content: center; }
        a.btn { display: inline-block; background: #38bdf8; color: #0f172a; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: 700; transition: background 0.2s; }
        a.btn:hover { background: #7dd3fc; }
    </style>
</head>
<body>
    <div class="card">
        <h1>🚀 Daily Job Aggregator</h1>
        <p>Status: <span class="badge">Online</span></p>
        <p>Vercel Serverless Function entry point is active and ready.</p>
        <div class="actions">
            <a href="/?run=true" class="btn">⚡ Trigger Job Aggregator</a>
        </div>
    </div>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_response.encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"Error: {str(e)}".encode("utf-8"))


# Top-level entrypoints required by Vercel CLI
app = handler
application = handler


def main():
    parser = argparse.ArgumentParser(description="Daily Job Aggregator - Pythonic Job Scraper & Email Digest")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config.yaml file")
    parser.add_argument("--dry-run", action="store_true", help="Run scrapers and render preview without sending emails")
    parser.add_argument("--server", action="store_true", help="Launch Web Dashboard and API server")
    parser.add_argument("--port", type=int, default=8000, help="Port for Web Dashboard server (default: 8000)")
    args = parser.parse_args()

    if args.server:
        from server import run_server
        run_server(args.port)
        return

    config_path = Path(args.config)
    config = load_config(config_path)

    asyncio.run(run_pipeline(config, dry_run=args.dry_run))


if __name__ == "__main__":
    main()


