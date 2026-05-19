from .base_agent import ask_ollama, parse_json_response
import requests

PROMETHEUS_URL = "http://localhost:9090"

def get_prometheus_metric(query):
    """Nolasa reālu metriku no Prometheus API."""
    try:
        r = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=5
        )
        data = r.json()
        results = data.get("data", {}).get("result", [])
        if results:
            return float(results[0]["value"][1])
    except:
        pass
    return None

SYSTEM = """You are a DevOps infrastructure agent. You receive the delivery agent's 
decision and real Prometheus metrics to evaluate infrastructure readiness.
Reply ONLY with a JSON object, no other text."""

def analyze(data, delivery_result=None):
    # Nolasa reālas Prometheus metrikas
    stable_error = get_prometheus_metric('app_error_rate{version="1.0.0"}')
    canary_error = get_prometheus_metric('app_error_rate{version="2.0.0"}')
    stable_latency = get_prometheus_metric('app_latency_ms{version="1.0.0"}')
    canary_latency = get_prometheus_metric('app_latency_ms{version="2.0.0"}')

    # Ja Prometheus nav pieejams, izmanto pipeline datus
    if stable_error is None:
        stable_error = data.get("stable_error_rate", 0)
    if canary_error is None:
        canary_error = data.get("canary_error_rate", 0)
    if stable_latency is None:
        stable_latency = data.get("stable_latency_ms", 50)
    if canary_latency is None:
        canary_latency = data.get("canary_latency_ms", 50)

    docker_logs = data.get("docker_logs", "")

    # Saņem piegādes aģenta JSON (ķēde)
    prev_context = ""
    if delivery_result:
        prev_context = f"""
DELIVERY AGENT DECISION (received via agent chain):
  Decision: {delivery_result.get("decision", "unknown")}
  Risk level: {delivery_result.get("risk_level", "unknown")}
  Reason: {delivery_result.get("reason", "")}
  Blocking issues: {delivery_result.get("blocking_issues", [])}
"""

    prompt = f"""Infrastructure readiness evaluation:
{prev_context}
REAL PROMETHEUS METRICS:
  Stable container (v1.0.0):
    Error rate: {stable_error:.1%}
    Latency: {stable_latency:.0f}ms

  Canary container (v2.0.0):
    Error rate: {canary_error:.1%}
    Latency: {canary_latency:.0f}ms

DOCKER LOGS (resource indicators):
{docker_logs[-300:] if docker_logs else "No logs"}

Based on Prometheus metrics and delivery agent decision, evaluate:
- Is infrastructure stable enough for deployment?
- Are there resource exhaustion signs?
- Does canary show acceptable performance?

Reply with this exact JSON:
{{
  "ready": true or false,
  "reason": "explanation based on real Prometheus metrics",
  "resource_status": "OK", "WARNING" or "CRITICAL",
  "stable_error_rate": {stable_error:.4f},
  "canary_error_rate": {canary_error:.4f},
  "risk_note": "infrastructure risk assessment"
}}"""

    response, elapsed = ask_ollama(prompt, SYSTEM)
    parsed = parse_json_response(response)
    parsed["agent"] = "infra"
    parsed["llm_time_sec"] = elapsed
    return parsed