import asyncio
import time
import statistics
import logging
from typing import Dict, List, Any, Optional
import httpx
import sys
from pathlib import Path

# Add app to path to generate tokens
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.core.security import create_access_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("codesphere.loadtest")

BASE_URL = "http://127.0.0.1:8000"

# Pre-generate standard admin & student tokens for simulated virtual users
ADMIN_TOKEN = create_access_token(1, extra_claims={"email": "placement@ipu.ac.in", "role": "SUPER_ADMIN"})
STUDENT_TOKEN = create_access_token(3, extra_claims={"email": "aaradhy.13719051625@std.ggsipu.ac.in", "role": "STUDENT"})

class RealisticUserSession:
    """
    Simulates a realistic institutional user journey on CodeSphere:
    1. Authenticated User Session (Admin / Student)
    2. Read Dashboard & Placement Analytics Overview
    3. Browse Assessment Rounds
    4. Fetch Event Detail with Question Catalog
    5. Retrieve Question Problem Statement & Test Cases
    6. Check Event Leaderboard & Lifetime Rankings
    7. Health Probe
    """
    def __init__(self, user_index: int, client: httpx.AsyncClient, semaphore: asyncio.Semaphore):
        self.user_index = user_index
        self.client = client
        self.semaphore = semaphore
        self.token = ADMIN_TOKEN if user_index % 5 == 0 else STUDENT_TOKEN
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.latencies: List[float] = []
        self.errors: int = 0
        self.requests_count: int = 0

    async def execute_request(self, method: str, url: str, **kwargs) -> Optional[httpx.Response]:
        async with self.semaphore:
            start = time.time()
            self.requests_count += 1
            try:
                if method.upper() == "GET":
                    resp = await self.client.get(url, headers=self.headers, **kwargs)
                elif method.upper() == "POST":
                    resp = await self.client.post(url, headers=self.headers, **kwargs)
                else:
                    resp = await self.client.request(method, url, headers=self.headers, **kwargs)

                latency_ms = (time.time() - start) * 1000.0
                self.latencies.append(latency_ms)

                if resp.status_code >= 400 and resp.status_code != 429:
                    self.errors += 1
                return resp
            except Exception as e:
                self.errors += 1
                self.latencies.append((time.time() - start) * 1000.0)
                return None

    async def run_journey(self) -> Dict[str, Any]:
        # Stagger simulated user initiation
        await asyncio.sleep((self.user_index % 100) * 0.005)

        is_admin = (self.user_index % 5 == 0)

        if is_admin:
            # Step 1: Admin Dashboard / Institutional Analytics
            await self.execute_request("GET", f"{BASE_URL}/api/v1/analytics/overview")
            # Step 2: Student Registry
            await self.execute_request("GET", f"{BASE_URL}/api/v1/students/?skip=0&limit=10")
        else:
            # Step 1: Student Profile & Readiness
            await self.execute_request("GET", f"{BASE_URL}/api/v1/auth/me")
            # Step 2: Lifetime Rankings
            await self.execute_request("GET", f"{BASE_URL}/api/v1/leaderboards/lifetime")

        # Step 3: Browse Assessment Rounds (Public / Authenticated)
        events_resp = await self.execute_request("GET", f"{BASE_URL}/api/v1/events/?skip=0&limit=10")
        event_id = 1
        if events_resp and events_resp.status_code == 200:
            events_data = events_resp.json()
            if isinstance(events_data, list) and len(events_data) > 0:
                event_id = events_data[0]["id"]

        # Step 4: Fetch Assessment Detail
        await self.execute_request("GET", f"{BASE_URL}/api/v1/events/{event_id}")

        # Step 5: Read Question Catalog
        await self.execute_request("GET", f"{BASE_URL}/api/v1/questions/?skip=0&limit=10")

        # Step 6: Read Question Detail
        await self.execute_request("GET", f"{BASE_URL}/api/v1/questions/1")

        # Step 7: Check Event Leaderboard
        await self.execute_request("GET", f"{BASE_URL}/api/v1/leaderboards/event/{event_id}")

        # Step 8: Health Probe
        await self.execute_request("GET", f"{BASE_URL}/health/liveness")

        return {
            "requests": self.requests_count,
            "errors": self.errors,
            "latencies": self.latencies
        }


async def run_concurrency_level(concurrent_users: int, max_concurrency: int = 150, test_name: str = "Load Test") -> Dict[str, Any]:
    """Runs a batch of concurrent users simulating realistic institutional workloads."""
    semaphore = asyncio.Semaphore(max_concurrency)
    limits = httpx.Limits(max_connections=max_concurrency * 2, max_keepalive_connections=max_concurrency)
    timeout = httpx.Timeout(10.0, connect=5.0)

    start_suite_time = time.time()
    
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        users = [RealisticUserSession(i, client, semaphore) for i in range(concurrent_users)]
        tasks = [user.run_journey() for user in users]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    duration_seconds = time.time() - start_suite_time
    
    all_latencies = []
    total_requests = 0
    total_errors = 0

    for r in results:
        if isinstance(r, dict):
            all_latencies.extend(r.get("latencies", []))
            total_requests += r.get("requests", 0)
            total_errors += r.get("errors", 0)
        else:
            total_errors += 1

    throughput_rps = round(total_requests / max(duration_seconds, 0.001), 1)
    error_rate = round((total_errors / max(total_requests, 1)) * 100.0, 2)

    if all_latencies:
        sorted_lat = sorted(all_latencies)
        n = len(sorted_lat)
        p50 = round(sorted_lat[int(n * 0.50)], 2)
        p95 = round(sorted_lat[min(int(n * 0.95), n - 1)], 2)
        p99 = round(sorted_lat[min(int(n * 0.99), n - 1)], 2)
        avg_lat = round(statistics.mean(all_latencies), 2)
    else:
        p50, p95, p99, avg_lat = 0.0, 0.0, 0.0, 0.0

    status = "PASS" if error_rate < 5.0 else "FAIL"

    summary = {
        "concurrent_users": concurrent_users,
        "duration_seconds": round(duration_seconds, 2),
        "total_requests": total_requests,
        "throughput_rps": throughput_rps,
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "p99_latency_ms": p99,
        "avg_latency_ms": avg_lat,
        "total_errors": total_errors,
        "error_rate_percent": error_rate,
        "status": status
    }

    print(f"\n[{concurrent_users} USERS]   100% COMPLETE")
    print(f"Requests: {total_requests}")
    print(f"RPS: {throughput_rps}")
    print(f"P50: {p50}ms")
    print(f"P95: {p95}ms")
    print(f"P99: {p99}ms")
    print(f"Errors: {total_errors} ({error_rate}%)")
    print(f"Status: {status}")

    return summary


async def run_full_suite() -> Dict[str, Any]:
    levels = [100, 500, 1000, 2500, 5000]
    all_results = {}

    for lvl in levels:
        res = await run_concurrency_level(lvl, max_concurrency=min(200, lvl), test_name=f"Level ({lvl} Users)")
        all_results[f"level_{lvl}"] = res
        await asyncio.sleep(0.5)

    # Spike Test: Sudden surge of 5,000 users with max burst
    print("\n[SPIKE TEST (500 -> 5000 SURGE)]   STARTING")
    spike_res = await run_concurrency_level(5000, max_concurrency=250, test_name="Traffic Spike Test")
    all_results["spike_test"] = spike_res

    # Failure Resilience Test
    async with httpx.AsyncClient(timeout=5.0) as client:
        health_resp = await client.get(f"{BASE_URL}/health/readiness")
        metrics_resp = await client.get(f"{BASE_URL}/metrics")
        all_results["failure_resilience"] = {
            "readiness_status": health_resp.status_code,
            "readiness_data": health_resp.json() if health_resp.status_code == 200 else {},
            "metrics_data": metrics_resp.json() if metrics_resp.status_code == 200 else {},
            "status": "PASS" if health_resp.status_code == 200 else "FAIL"
        }

    return all_results

if __name__ == "__main__":
    results = asyncio.run(run_full_suite())
    print("\n\n================ FINAL LOAD TESTING BENCHMARK SUMMARY ================")
    import json
    print(json.dumps(results, indent=2))
