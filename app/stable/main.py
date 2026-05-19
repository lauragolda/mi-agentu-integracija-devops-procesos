from flask import Flask, jsonify
import time, os

app = Flask(__name__)
VERSION = "1.0.0"

request_count = {"health": 0, "data": 0, "users": 0, "orders": 0}
error_count = {"health": 0, "data": 0, "users": 0, "orders": 0}
latency_sum = {"health": 0.0, "data": 0.0, "users": 0.0, "orders": 0.0}

@app.route("/health")
def health():
    start = time.time()
    request_count["health"] += 1
    latency_sum["health"] += (time.time() - start) * 1000
    return jsonify({"status": "ok", "version": VERSION})

@app.route("/api/data")
def data():
    start = time.time()
    request_count["data"] += 1
    time.sleep(0.05)
    latency_sum["data"] += (time.time() - start) * 1000
    return jsonify({"data": "ok", "version": VERSION})

@app.route("/api/users")
def users():
    start = time.time()
    request_count["users"] += 1
    time.sleep(0.05)
    latency_sum["users"] += (time.time() - start) * 1000
    return jsonify({"users": ["alice", "bob"], "version": VERSION})

@app.route("/api/orders")
def orders():
    start = time.time()
    request_count["orders"] += 1
    time.sleep(0.05)
    latency_sum["orders"] += (time.time() - start) * 1000
    return jsonify({"orders": [1, 2, 3], "version": VERSION})

@app.route("/metrics")
def metrics():
    total_requests = sum(request_count.values())
    total_errors = sum(error_count.values())
    error_rate = total_errors / max(total_requests, 1)
    avg_latency = sum(latency_sum.values()) / max(total_requests, 1)

    return f"""# HELP app_requests_total Total requests
# TYPE app_requests_total counter
app_requests_total{{version="{VERSION}"}} {total_requests}
# HELP app_errors_total Total errors
# TYPE app_errors_total counter
app_errors_total{{version="{VERSION}"}} {total_errors}
# HELP app_error_rate Error rate
# TYPE app_error_rate gauge
app_error_rate{{version="{VERSION}"}} {error_rate:.4f}
# HELP app_latency_ms Average latency ms
# TYPE app_latency_ms gauge
app_latency_ms{{version="{VERSION}"}} {avg_latency:.2f}
# HELP app_up Application status
# TYPE app_up gauge
app_up{{version="{VERSION}"}} 1
""", 200, {"Content-Type": "text/plain"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)