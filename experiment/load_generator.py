import requests
import threading
import time

NGINX_URL = "http://localhost:8080"
STABLE_URL = "http://localhost:5000"
CANARY_URL = "http://localhost:5001"

def generate_load(url, count=100, results=None):
    errors = 0
    latencies = []
    for _ in range(count):
        try:
            start = time.time()
            r = requests.get(f"{url}/api/data", timeout=5)
            latencies.append((time.time() - start) * 1000)
            if r.status_code != 200:
                errors += 1
        except:
            errors += 1
            latencies.append(5000)

    error_rate = round(errors / count, 4)
    avg_latency = round(sum(latencies) / len(latencies), 1)
    p95_latency = round(sorted(latencies)[int(len(latencies) * 0.95)], 1)

    if results is not None:
        results["error_rate"] = error_rate
        results["avg_latency"] = avg_latency
        results["p95_latency"] = p95_latency
        results["errors"] = errors
        results["total"] = count

def measure_with_load(requests_count=100):
    nginx_results = {}
    stable_results = {}
    canary_results = {}

    threads = [
        threading.Thread(target=generate_load,
                        args=(NGINX_URL, requests_count, nginx_results)),
        threading.Thread(target=generate_load,
                        args=(STABLE_URL, requests_count // 2, stable_results)),
        threading.Thread(target=generate_load,
                        args=(CANARY_URL, requests_count // 2, canary_results)),
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print(f"  [Load] Nginx (80/20): errors={nginx_results.get('error_rate', 0):.0%}, "
          f"latency={nginx_results.get('avg_latency', 0):.0f}ms")
    print(f"  [Load] Stable direct: errors={stable_results.get('error_rate', 0):.0%}, "
          f"latency={stable_results.get('avg_latency', 0):.0f}ms")
    print(f"  [Load] Canary direct: errors={canary_results.get('error_rate', 0):.0%}, "
          f"latency={canary_results.get('avg_latency', 0):.0f}ms")

    return {
        "nginx_error_rate": nginx_results.get("error_rate", 0),
        "nginx_latency_ms": nginx_results.get("avg_latency", 0),
        "nginx_p95_latency_ms": nginx_results.get("p95_latency", 0),
        "stable_error_rate": stable_results.get("error_rate", 0),
        "stable_latency_ms": stable_results.get("avg_latency", 0),
        "canary_error_rate": canary_results.get("error_rate", 0),
        "canary_latency_ms": canary_results.get("avg_latency", 0),
    }

if __name__ == "__main__":
    print("=== Load Generator Test ===")
    results = measure_with_load(100)
    print("\nResults:")
    for k, v in results.items():
        print(f"  {k}: {v}")
