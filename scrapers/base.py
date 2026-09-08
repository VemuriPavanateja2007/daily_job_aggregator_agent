import abc
import logging
import re
from typing import List
from core.models import JobPosting, BrowserSettings

logger = logging.getLogger("JobAggregator.Fetcher")


class BaseFetcher(abc.ABC):
    """
    Abstract Base Class for all platform job fetchers.
    Enforces a unified async interface and shared date parsing utilities.
    """

    def __init__(self, platform_name: str, browser_settings: BrowserSettings):
        self.platform_name = platform_name
        self.browser_settings = browser_settings
        self.logger = logging.getLogger(f"JobAggregator.Fetcher.{platform_name}")

    @abc.abstractmethod
    async def fetch_jobs(self, search_term: str, location: str) -> List[JobPosting]:
        """
        Fetch job postings for a specified role and location.

        :param search_term: Role title (e.g. "Data Scientist")
        :param location: Target location (e.g. "Remote")
        :return: List of validated JobPosting objects
        """
        pass

    @staticmethod
    def parse_posted_hours(text: str) -> float:
        """
        Convert human-readable posting age text into numerical hours.
        Examples:
          - "2 hours ago" -> 2.0
          - "1 day ago" / "Yesterday" -> 24.0
          - "30 minutes ago" -> 0.5
          - "3 days ago" -> 72.0
          - "Just posted" -> 0.1
        """
        if not text:
            return 12.0  # Default fallback

        lower_text = text.lower().strip()

        if "just" in lower_text or "minute" in lower_text or "moments" in lower_text:
            match = re.search(r"(\d+)", lower_text)
            if match:
                return round(float(match.group(1)) / 60.0, 2)
            return 0.25

        if "hour" in lower_text:
            match = re.search(r"(\d+)", lower_text)
            if match:
                return float(match.group(1))
            return 1.0

        if "day" in lower_text or "yesterday" in lower_text:
            if "yesterday" in lower_text:
                return 24.0
            match = re.search(r"(\d+)", lower_text)
            if match:
                return float(match.group(1)) * 24.0
            return 24.0

        if "week" in lower_text:
            match = re.search(r"(\d+)", lower_text)
            if match:
                return float(match.group(1)) * 168.0
            return 168.0

        return 12.0
