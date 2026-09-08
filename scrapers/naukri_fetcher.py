import asyncio
import urllib.parse
from typing import List
from scrapers.base import BaseFetcher
from core.models import JobPosting


class NaukriFetcher(BaseFetcher):
    """
    Async Playwright fetcher for Naukri.com job postings.
    Utilizes freshness parameter (freshness=1 for past 24h) and headless browser automation.
    """

    def __init__(self, browser_settings):
        super().__init__("Naukri", browser_settings)

    async def fetch_jobs(self, search_term: str, location: str) -> List[JobPosting]:
        self.logger.info(f"Fetching Naukri jobs for '{search_term}' in '{location}'...")

        slug_term = search_term.lower().replace(" ", "-")
        slug_loc = location.lower().replace(" ", "-")
        url = f"https://www.naukri.com/{slug_term}-jobs-in-{slug_loc}?freshness=1"

        job_postings: List[JobPosting] = []

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            self.logger.error("Playwright is not installed.")
            return job_postings

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.browser_settings.headless,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
                )

                context = await browser.new_context(
                    user_agent=self.browser_settings.user_agent,
                    viewport={"width": 1920, "height": 1080}
                )

                page = await context.new_page()

                try:
                    from playwright_stealth import stealth_async
                    await stealth_async(page)
                except Exception:
                    pass

                self.logger.debug(f"Navigating to Naukri: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=self.browser_settings.timeout_ms)
                await asyncio.sleep(3)

                # Scroll down to load jobs dynamically
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(2)

                cards = await page.query_selector_all(".srp-jobtuple-wrapper, div.cust-job-tuple, article.jobTuple")

                for card in cards:
                    try:
                        title_el = await card.query_selector("a.title, .title")
                        title = (await title_el.inner_text()).strip() if title_el else ""
                        href = await title_el.get_attribute("href") if title_el else ""

                        company_el = await card.query_selector("a.comp-name, .subTitle, .comp-name")
                        company = (await company_el.inner_text()).strip() if company_el else ""

                        location_el = await card.query_selector("span.locWraper, .location, .loc-wrap")
                        loc = (await location_el.inner_text()).strip() if location_el else location

                        time_el = await card.query_selector(".job-post-day, .type, .job-type")
                        time_text = (await time_el.inner_text()).strip() if time_el else "1 day ago"

                        is_sponsored = "sponsored" in (await card.inner_text()).lower()

                        if title and company and href:
                            hours_ago = self.parse_posted_hours(time_text)
                            job_postings.append(
                                JobPosting(
                                    title=title,
                                    company=company,
                                    location=loc,
                                    url=href if href.startswith("http") else f"https://www.naukri.com{href}",
                                    source="Naukri",
                                    posted_text=time_text,
                                    posted_hours_ago=hours_ago,
                                    is_sponsored=is_sponsored
                                )
                            )
                    except Exception as card_err:
                        self.logger.debug(f"Error parsing Naukri job card: {card_err}")
                        continue

                await browser.close()

        except Exception as e:
            self.logger.error(f"Naukri fetch failed with error: {e}. Gracefully continuing...")

        self.logger.info(f"Successfully retrieved {len(job_postings)} jobs from Naukri.")
        return job_postings
