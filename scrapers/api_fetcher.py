import aiohttp
from typing import List
from scrapers.base import BaseFetcher
from core.models import JobPosting, RapidAPIConfig


class RapidAPIFetcher(BaseFetcher):
    """
    API-backed job fetcher using RapidAPI JSearch or equivalent aggregator.
    Provides 100% reliable data ingestion without web scraping risks.
    """

    def __init__(self, browser_settings, api_config: RapidAPIConfig):
        super().__init__("RapidAPI", browser_settings)
        self.api_config = api_config

    async def fetch_jobs(self, search_term: str, location: str) -> List[JobPosting]:
        if not self.api_config.api_key:
            self.logger.warning("RapidAPI key not provided in config. Skipping API fetcher.")
            return []

        self.logger.info(f"Fetching API jobs for '{search_term}' in '{location}'...")

        url = "https://jsearch.p.rapidapi.com/search"
        querystring = {
            "query": f"{search_term} in {location}",
            "page": "1",
            "num_pages": "1",
            "date_posted": "today"  # Filter for last 24h
        }

        headers = {
            "X-RapidAPI-Key": self.api_config.api_key,
            "X-RapidAPI-Host": self.api_config.api_host
        }

        job_postings: List[JobPosting] = []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=querystring, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("data", [])

                        for item in results:
                            title = item.get("job_title", "")
                            company = item.get("employer_name", "")
                            loc = f"{item.get('job_city', '')}, {item.get('job_country', '')}".strip(", ")
                            apply_link = item.get("job_apply_link") or item.get("job_google_link", "")

                            if title and company and apply_link:
                                job_postings.append(
                                    JobPosting(
                                        title=title,
                                        company=company,
                                        location=loc or location,
                                        url=apply_link,
                                        source="RapidAPI Aggregator",
                                        posted_text="Within 24 hours",
                                        posted_hours_ago=12.0
                                    )
                                )
                    else:
                        self.logger.error(f"RapidAPI request failed with status code {resp.status}")

        except Exception as e:
            self.logger.error(f"RapidAPI fetch failed: {e}")

        self.logger.info(f"Retrieved {len(job_postings)} jobs via RapidAPI.")
        return job_postings
