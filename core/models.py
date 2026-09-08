import hashlib
import re
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class JobPosting(BaseModel):
    """
    Standardized schema for job postings across all source platforms.
    Includes automated sanitization and unique hash generation.
    """
    job_id: str = Field(default="", description="Unique SHA256 identifier based on title, company, and location")
    title: str = Field(..., description="Job role title")
    company: str = Field(..., description="Company name")
    location: str = Field(..., description="Job location or Remote status")
    url: str = Field(..., description="Direct link to the job application")
    source: str = Field(..., description="Platform source (e.g. LinkedIn, Naukri, Glassdoor)")
    posted_text: str = Field(default="Recently", description="Raw posting date text (e.g., '2 hours ago')")
    posted_hours_ago: float = Field(default=0.0, description="Parsed numerical age of posting in hours")
    is_sponsored: bool = Field(default=False, description="Flag indicating sponsored/promoted posting")
    description_snippet: Optional[str] = Field(default=None, description="Short job summary or snippet")
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("title", "company", "location", mode="before")
    @classmethod
    def clean_text(cls, v: str) -> str:
        if not v:
            return "N/A"
        # Strip excessive whitespace and line breaks
        cleaned = re.sub(r"\s+", " ", str(v)).strip()
        return cleaned

    @field_validator("url", mode="before")
    @classmethod
    def clean_url(cls, v: str) -> str:
        if not v:
            return ""
        # Remove tracking parameters where applicable
        url_str = str(v).strip()
        if "?" in url_str and "linkedin.com" in url_str:
            url_str = url_str.split("?")[0]
        return url_str

    def model_post_init(self, __context: Any) -> None:
        """Generate deterministic job_id if not explicitly provided."""
        if not self.job_id:
            normalized_str = f"{self.title.lower()}|{self.company.lower()}|{self.location.lower()}"
            self.job_id = hashlib.sha256(normalized_str.encode("utf-8")).hexdigest()[:16]


class BrowserSettings(BaseModel):
    headless: bool = True
    timeout_ms: int = 30000
    slow_mo_ms: int = 1000
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


class EmailConfig(BaseModel):
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    sender_email: str = ""
    sender_password: str = ""
    recipient_email: str = ""
    send_digest: bool = False


class RapidAPIConfig(BaseModel):
    api_key: str = ""
    api_host: str = "jsearch.p.rapidapi.com"


class AggregatorConfig(BaseModel):
    target_roles: List[str]
    locations: List[str]
    max_age_hours: float = 24.0
    enabled_platforms: Dict[str, bool]
    browser_settings: BrowserSettings = Field(default_factory=BrowserSettings)
    email: EmailConfig = Field(default_factory=EmailConfig)
    rapidapi: RapidAPIConfig = Field(default_factory=RapidAPIConfig)
