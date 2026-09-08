import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import JobPosting
from core.processor import DataProcessor
from core.notifier import EmailNotifier
from core.models import EmailConfig


def test_pipeline():
    print("Testing JobPosting validation...")
    job1 = JobPosting(
        title="  Senior Machine Learning Engineer  ",
        company="TechCorp Inc.",
        location="Remote ",
        url="https://www.linkedin.com/jobs/view/12345?refId=xyz&trackingId=abc",
        source="LinkedIn",
        posted_text="2 hours ago",
        posted_hours_ago=2.0
    )

    # Verify cleaning
    assert job1.title == "Senior Machine Learning Engineer"
    assert job1.company == "TechCorp Inc."
    assert job1.url == "https://www.linkedin.com/jobs/view/12345"
    assert job1.job_id != ""
    print("[OK] Model cleaning & hashing verified.")


    # Duplicate job posting on another platform
    job2 = JobPosting(
        title="Senior Machine Learning Engineer",
        company="TechCorp",
        location="Remote",
        url="https://www.naukri.com/job/12345",
        source="Naukri",
        posted_text="3 hours ago",
        posted_hours_ago=3.0
    )

    # Older job (>24h)
    job3 = JobPosting(
        title="Data Scientist",
        company="OldData LLC",
        location="India",
        url="https://www.glassdoor.com/job/999",
        source="Glassdoor",
        posted_text="3 days ago",
        posted_hours_ago=72.0
    )

    # Sponsored job
    job4 = JobPosting(
        title="AI Engineer",
        company="AdCompany",
        location="Remote",
        url="https://www.linkedin.com/jobs/view/777",
        source="LinkedIn",
        posted_text="1 hour ago",
        posted_hours_ago=1.0,
        is_sponsored=True
    )

    raw_jobs = [job1, job2, job3, job4]
    processor = DataProcessor(max_age_hours=24.0)
    clean_jobs = processor.process(raw_jobs)

    # Expectations:
    # - job3 filtered out (72h > 24h)
    # - job4 filtered out (is_sponsored=True)
    # - job1 and job2 deduplicated to 1 listing
    assert len(clean_jobs) == 1
    assert clean_jobs[0].title == "Senior Machine Learning Engineer"
    print("[OK] DataProcessor deduplication & 24h filtering verified.")

    # Test Email Rendering
    template_dir = Path(__file__).parent.parent / "templates"
    notifier = EmailNotifier(EmailConfig(), template_dir)
    html = notifier.render_digest(clean_jobs, ["Machine Learning Engineer"])
    assert "Senior Machine Learning Engineer" in html
    assert "Daily Job Digest" in html
    print("[OK] Jinja2 HTML rendering verified.")

    print("\nALL UNIT TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_pipeline()
