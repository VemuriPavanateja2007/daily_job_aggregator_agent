import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader
from core.models import EmailConfig, JobPosting

logger = logging.getLogger("JobAggregator.Notifier")


class EmailNotifier:
    """
    Email notification dispatcher utilizing Jinja2 HTML rendering and SMTP.
    """

    def __init__(self, config: EmailConfig, template_dir: Path):
        self.config = config
        self.template_dir = template_dir
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True
        )

    def render_digest(self, jobs: List[JobPosting], target_roles: List[str]) -> str:
        """Render jobs into HTML string using Jinja2 template."""
        template = self.jinja_env.get_template("digest_template.html")
        rendered_html = template.render(
            jobs=jobs,
            target_roles=target_roles,
            total_count=len(jobs),
            generated_date=datetime.now().strftime("%B %d, %Y")
        )
        return rendered_html

    def send_email(self, html_content: str, subject: str = "Daily Job Digest") -> bool:
        """
        Send HTML digest via SMTP. If send_digest is False, save local preview.
        """
        # Save local preview regardless for audit
        preview_path = Path("digest_preview.html")
        preview_path.write_text(html_content, encoding="utf-8")
        logger.info(f"Saved local HTML digest preview to: {preview_path.resolve()}")

        if not self.config.send_digest:
            logger.info("Email dispatch disabled in config (send_digest=false). Skipping SMTP transmission.")
            return True

        if not self.config.sender_email or not self.config.sender_password:
            logger.warning("SMTP sender email or password not configured. Email skipped.")
            return False

        try:
            logger.info(f"Connecting to SMTP server {self.config.smtp_server}:{self.config.smtp_port}...")
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.config.sender_email
            msg["To"] = self.config.recipient_email or self.config.sender_email

            part_html = MIMEText(html_content, "html")
            msg.attach(part_html)

            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                server.starttls()
                server.login(self.config.sender_email, self.config.sender_password)
                server.sendmail(self.config.sender_email, [msg["To"]], msg.as_string())

            logger.info(f"Successfully sent daily job digest email to {msg['To']}.")
            return True

        except Exception as e:
            logger.error(f"Failed to dispatch email via SMTP: {e}")
            return False
