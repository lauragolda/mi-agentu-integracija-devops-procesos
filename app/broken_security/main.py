from flask import Flask, jsonify, request
import time, subprocess, os

app = Flask(__name__)
VERSION = "2.5.0-broken-security"

request_count = {"health": 0, "data": 0, "users": 0, "orders": 0}
error_count = {"health": 0, "data": 0, "users": 0, "orders": 0}
latency_sum = {"health": 0.0, "data": 0.0, "users": 0.0, "orders": 0.0}

# Bandit B105: hardcoded password
SECRET_KEY = "admin123"
DB_PASSWORD = "password123"

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
    # Bandit B307: use of eval
    user_input = request.args.get("filter", "True")
    result = eval(user_input)
    time.sleep(0.05)
    latency_sum["data"] += (time.time() - start) * 1000
    return jsonify({"data": "ok", "version": VERSION, "filter": str(result)})

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
    # Bandit B602: subprocess with shell=True
    order_id = request.args.get("id", "1")
    subprocess.run(f"echo order_{order_id}", shell=True, capture_output=True)
    time.sleep(0.05)
    latency_sum["orders"] += (time.time() - start) * 1000
    return jsonify({"orders": [1, 2, 3], "version": VERSION})

@app.route("/metrics")
def metrics():
    total_requests = sum(request_count.values())
    total_errors = sum(error_count.values())
    error_rate = total_errors / max(total_requests, 1)
    avg_latency = sum(latency_sum.values()) / max(total_requests, 1)

    return f"""# HELP app_error_rate Error rate
# TYPE app_error_rate gauge
app_error_rate{{version="{VERSION}"}} {error_rate:.4f}
# HELP app_latency_ms Average latency
# TYPE app_latency_ms gauge
app_latency_ms{{version="{VERSION}"}} {avg_latency:.2f}
# HELP app_up Application status
# TYPE app_up gauge
app_up{{version="{VERSION}"}} 1
""", 200, {"Content-Type": "text/plain"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)