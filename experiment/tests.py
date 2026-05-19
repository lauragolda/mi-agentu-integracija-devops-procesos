import pytest
import requests
import time

BASE_URL = "http://localhost:5002"

def test_health_returns_200():
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    assert r.status_code == 200, f"Health failed: {r.status_code}"

def test_health_returns_ok_status():
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    data = r.json()
    assert data["status"] == "ok", f"Status not ok: {data}"

def test_health_returns_version():
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    assert "version" in r.json(), "No version field"

def test_data_endpoint_returns_200():
    r = requests.get(f"{BASE_URL}/api/data", timeout=5)
    assert r.status_code == 200, f"Data endpoint failed: {r.status_code}"

def test_data_endpoint_returns_data_field():
    r = requests.get(f"{BASE_URL}/api/data", timeout=5)
    assert "data" in r.json(), f"No data field: {r.json()}"

def test_users_endpoint_returns_200():
    r = requests.get(f"{BASE_URL}/api/users", timeout=5)
    assert r.status_code == 200, f"Users endpoint failed: {r.status_code}"

def test_users_endpoint_returns_list():
    r = requests.get(f"{BASE_URL}/api/users", timeout=5)
    assert "users" in r.json(), f"No users field: {r.json()}"

def test_orders_endpoint_returns_200():
    r = requests.get(f"{BASE_URL}/api/orders", timeout=5)
    assert r.status_code == 200, f"Orders endpoint failed: {r.status_code}"

def test_orders_endpoint_returns_list():
    r = requests.get(f"{BASE_URL}/api/orders", timeout=5)
    assert "orders" in r.json(), f"No orders field: {r.json()}"

def test_latency_under_300ms():
    times = []
    for _ in range(5):
        start = time.time()
        requests.get(f"{BASE_URL}/api/data", timeout=5)
        times.append((time.time() - start) * 1000)
    avg = sum(times) / len(times)
    assert avg < 300, f"Latency too high: {avg:.0f}ms"

def test_error_rate_under_10_percent():
    errors = 0
    total = 20
    for _ in range(total):
        r = requests.get(f"{BASE_URL}/api/data", timeout=5)
        if r.status_code != 200:
            errors += 1
    rate = errors / total
    assert rate < 0.10, f"Error rate too high: {rate:.0%}"

def test_users_error_rate_under_10_percent():
    errors = 0
    total = 20
    for _ in range(total):
        r = requests.get(f"{BASE_URL}/api/users", timeout=5)
        if r.status_code != 200:
            errors += 1
    rate = errors / total
    assert rate < 0.10, f"Users error rate too high: {rate:.0%}"
