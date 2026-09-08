import json
import sys
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server import run_server

PORT = 8089
BASE_URL = f"http://localhost:{PORT}"


def start_test_server():
    t = threading.Thread(target=run_server, args=(PORT,), daemon=True)
    t.start()
    time.sleep(1)


def make_request(path, method="GET", data=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode("utf-8") if data else None
    req = Request(url, data=body, headers=headers, method=method)
    with urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_server_api():
    print(f"Starting test server on port {PORT}...")
    start_test_server()

    # 1. Test GET /api/config
    cfg = make_request("/api/config")
    assert "target_roles" in cfg
    print("[OK] GET /api/config verified.")

    # 2. Test POST /api/roles/add
    res_add = make_request("/api/roles/add", "POST", {"role": "Test Automation Engineer"})
    assert "Test Automation Engineer" in res_add["target_roles"]
    print("[OK] POST /api/roles/add verified.")

    # 3. Test POST /api/roles/remove
    res_rem = make_request("/api/roles/remove", "POST", {"role": "Test Automation Engineer"})
    assert "Test Automation Engineer" not in res_rem["target_roles"]
    print("[OK] POST /api/roles/remove verified.")

    # 4. Test GET /api/jobs
    jobs_res = make_request("/api/jobs")
    assert "jobs" in jobs_res
    assert jobs_res["total"] >= 1
    print("[OK] GET /api/jobs verified.")

    # 5. Test POST /api/jobs/save
    save_res = make_request("/api/jobs/save", "POST", {
        "job": {
            "title": "Backend Python Developer",
            "company": "PyCorp",
            "location": "Remote",
            "url": "https://example.com/job/99",
            "source": "Test",
            "status": "Saved"
        }
    })
    assert any(j["title"] == "Backend Python Developer" for j in save_res["saved_jobs"])
    print("[OK] POST /api/jobs/save verified.")

    # 6. Test GET /api/stats
    stats = make_request("/api/stats")
    assert "total_jobs" in stats
    assert "active_roles" in stats
    print("[OK] GET /api/stats verified.")

    print("\nALL SERVER API TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_server_api()
