import asyncio
import urllib.parse
from typing import List
from scrapers.base import BaseFetcher
from core.models import JobPosting


class GlassdoorFetcher(BaseFetcher):
    """
    Async Playwright fetcher for Glassdoor job search results.
    Includes Cloudflare detection detection and graceful error recovery.
    """

    def __init__(self, browser_settings):
        super().__init__("Glassdoor", browser_settings)

    async def fetch_jobs(self, search_term: str, location: str) -> List[JobPosting]:
        self.logger.info(f"Fetching Glassdoor jobs for '{search_term}' in '{location}'...")

        encoded_keywords = urllib.parse.quote(search_term)
        url = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={encoded_keywords}&fromAge=1"

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

                self.logger.debug(f"Navigating to Glassdoor: {url}")
                response = await page.goto(url, wait_until="domcontentloaded", timeout=self.browser_settings.timeout_ms)

                # Check for Cloudflare / bot block screen
                title = await page.title()
                if "Just a moment" in title or "Access Denied" in title or (response and response.status in [403, 429]):
                    self.logger.warning("Glassdoor anti-bot protection triggered (Cloudflare block). Gracefully bypassing Glassdoor.")
                    await browser.close()
                    return job_postings

                await asyncio.sleep(3)
                cards = await page.query_selector_all("li[data-test='jobListing'], div[class*='JobCard']")

                for card in cards:
                    try:
                        title_el = await card.query_selector("a[data-test='job-title'], a[class*='JobTitle']")
                        title_text = (await title_el.inner_text()).strip() if title_el else ""
                        href = await title_el.get_attribute("href") if title_el else ""

                        company_el = await card.query_selector("span[class*='EmployerName'], div[class*='Employer']")
                        company_text = (await company_el.inner_text()).strip() if company_el else ""

                        location_el = await card.query_selector("div[data-test='emp-location'], span[class*='Location']")
                        loc_text = (await location_el.inner_text()).strip() if location_el else location

                        time_el = await card.query_selector("div[data-test='job-age']")
                        time_text = (await time_el.inner_text()).strip() if time_el else "24h"

                        if title_text and company_text and href:
                            full_url = href if href.startswith("http") else f"https://www.glassdoor.com{href}"
                            hours_ago = self.parse_posted_hours(time_text)

                            job_postings.append(
                                JobPosting(
                                    title=title_text,
                                    company=company_text,
                                    location=loc_text,
                                    url=full_url,
                                    source="Glassdoor",
                                    posted_text=time_text,
                                    posted_hours_ago=hours_ago
                                )
                            )
                    except Exception as card_err:
                        self.logger.debug(f"Error parsing Glassdoor card: {card_err}")
                        continue

                await browser.close()

        except Exception as e:
            self.logger.warning(f"Glassdoor fetch encountered issue: {e}. Gracefully continuing with other sources...")

        self.logger.info(f"Successfully retrieved {len(job_postings)} jobs from Glassdoor.")
        return job_postings
