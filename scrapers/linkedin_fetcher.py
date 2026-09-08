import asyncio
import urllib.parse
from typing import List
from scrapers.base import BaseFetcher
from core.models import JobPosting


class LinkedInFetcher(BaseFetcher):
    """
    Async Playwright fetcher for public LinkedIn job search results.
    Bypasses auth wall using guest search endpoint with 24h filter (f_TPR=r86400).
    """

    def __init__(self, browser_settings):
        super().__init__("LinkedIn", browser_settings)

    async def fetch_jobs(self, search_term: str, location: str) -> List[JobPosting]:
        self.logger.info(f"Fetching LinkedIn jobs for '{search_term}' in '{location}'...")

        encoded_keywords = urllib.parse.quote(search_term)
        encoded_location = urllib.parse.quote(location)
        # f_TPR=r86400 filters jobs posted in the past 24 hours (86,400 seconds)
        url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_keywords}&location={encoded_location}&f_TPR=r86400"

        job_postings: List[JobPosting] = []

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            self.logger.error("Playwright is not installed. Run 'pip install playwright && playwright install'")
            return job_postings

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.browser_settings.headless,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
                )

                context = await browser.new_context(
                    user_agent=self.browser_settings.user_agent,
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US"
                )

                page = await context.new_page()

                # Attempt stealth plugin if available
                try:
                    from playwright_stealth import stealth_async
                    await stealth_async(page)
                except Exception:
                    pass

                self.logger.debug(f"Navigating to LinkedIn: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=self.browser_settings.timeout_ms)
                await asyncio.sleep(2)

                # Scroll down slightly to trigger lazy-loaded job cards
                await page.evaluate("window.scrollBy(0, 800)")
                await asyncio.sleep(1)

                # Extract job elements from guest job search cards
                cards = await page.query_selector_all(".base-card, .job-search-card, li .base-search-card")

                for card in cards:
                    try:
                        title_el = await card.query_selector(".base-search-card__title, .job-search-card__title, h3")
                        title = (await title_el.inner_text()).strip() if title_el else ""

                        company_el = await card.query_selector(".base-search-card__subtitle, .job-search-card__subtitle, h4")
                        company = (await company_el.inner_text()).strip() if company_el else ""

                        location_el = await card.query_selector(".job-search-card__location, .base-search-card__metadata")
                        loc = (await location_el.inner_text()).strip() if location_el else location

                        link_el = await card.query_selector("a.base-card__full-link, a.job-search-card__link")
                        href = await link_el.get_attribute("href") if link_el else ""

                        time_el = await card.query_selector("time")
                        time_text = (await time_el.inner_text()).strip() if time_el else "24 hours ago"

                        is_sponsored = "Promoted" in (await card.inner_text())

                        if title and company and href:
                            hours_ago = self.parse_posted_hours(time_text)
                            job_postings.append(
                                JobPosting(
                                    title=title,
                                    company=company,
                                    location=loc,
                                    url=href.split("?")[0],  # Clean URL parameters
                                    source="LinkedIn",
                                    posted_text=time_text,
                                    posted_hours_ago=hours_ago,
                                    is_sponsored=is_sponsored
                                )
                            )
                    except Exception as card_err:
                        self.logger.debug(f"Error parsing single LinkedIn card: {card_err}")
                        continue

                await browser.close()

        except Exception as e:
            self.logger.error(f"LinkedIn fetch failed with error: {e}. Gracefully continuing...")

        self.logger.info(f"Successfully retrieved {len(job_postings)} jobs from LinkedIn.")
        return job_postings
