import logging
import re
from typing import List
from core.models import JobPosting

logger = logging.getLogger("JobAggregator.Processor")


class DataProcessor:
    """
    Data Cleaning, Deduplication, and Filtering Engine.
    Uses pure Python standard library for maximum portability and resilience.
    """

    def __init__(self, max_age_hours: float = 24.0):
        self.max_age_hours = max_age_hours

    def process(self, raw_postings: List[JobPosting]) -> List[JobPosting]:
        """
        Clean, filter, and deduplicate job postings.

        :param raw_postings: Raw list of JobPosting objects from scrapers
        :return: Deduplicated and 24h age-filtered JobPosting list
        """
        if not raw_postings:
            logger.info("DataProcessor received 0 job postings to process.")
            return []

        logger.info(f"Processing {len(raw_postings)} raw job postings...")

        # 1. Filter Sponsored Listings
        non_sponsored = [j for j in raw_postings if not j.is_sponsored]
        sponsored_count = len(raw_postings) - len(non_sponsored)
        if sponsored_count > 0:
            logger.info(f"Filtered out {sponsored_count} sponsored/promoted listings.")

        # 2. Filter by Posting Age (Strict 24h window constraint)
        within_24h = [j for j in non_sponsored if j.posted_hours_ago <= self.max_age_hours]
        logger.info(f"Retained {len(within_24h)} jobs posted within the last {self.max_age_hours} hours.")

        if not within_24h:
            return []

        # 3. Deduplication Engine
        seen_keys = set()
        seen_urls = set()
        deduped_postings: List[JobPosting] = []

        for job in within_24h:
            norm_title = self._normalize_title(job.title)
            norm_company = self._normalize_company(job.company)
            dedup_key = f"{norm_title}||{norm_company}"

            # Clean URL
            clean_url = job.url.strip()

            if dedup_key in seen_keys or clean_url in seen_urls:
                continue

            seen_keys.add(dedup_key)
            if clean_url:
                seen_urls.add(clean_url)
            deduped_postings.append(job)

        dedup_removed = len(within_24h) - len(deduped_postings)
        if dedup_removed > 0:
            logger.info(f"Deduplicated {dedup_removed} cross-posted listings across platforms.")

        # Sort by posting freshness (newest first)
        deduped_postings.sort(key=lambda x: x.posted_hours_ago)

        logger.info(f"Final clean dataset: {len(deduped_postings)} unique job postings ready for digest.")
        return deduped_postings

    @staticmethod
    def _normalize_company(company: str) -> str:
        if not company:
            return ""
        text = company.lower()
        # Remove corporate suffixes
        text = re.sub(r"\b(inc|ltd|llc|pvt|private|corp|corporation|gmbh|co)\b", "", text)
        text = re.sub(r"[^\w\s]", "", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _normalize_title(title: str) -> str:
        if not title:
            return ""
        text = title.lower()
        # Remove trailing tags
        text = re.sub(r"\([^)]*\)", "", text)
        text = re.sub(r"[^\w\s]", "", text)
        return re.sub(r"\s+", " ", text).strip()

