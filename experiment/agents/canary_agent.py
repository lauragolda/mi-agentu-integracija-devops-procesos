from .base_agent import ask_ollama, parse_json_response

SYSTEM = """You are a DevOps Canary deployment agent. Analyze real metrics from 
live Docker containers and decide whether to continue rollout or rollback.
Reply ONLY with a JSON object, no other text."""

def analyze(data):
    canary_error = data.get("canary_error_rate", 0)
    stable_error = data.get("stable_error_rate", 0)
    canary_latency = data.get("canary_latency_ms", 0)
    stable_latency = data.get("stable_latency_ms", 0)
    docker_logs = data.get("docker_logs", "")
    gh_status = data.get("gh_actions_status", "unknown")
    error_delta = canary_error - stable_error
    latency_delta_pct = (canary_latency - stable_latency) / max(stable_latency, 1) * 100

    prompt = f"""Canary deployment analysis based on REAL metrics from live Docker containers:

GITHUB ACTIONS STATUS: {gh_status}

STABLE VERSION (baseline, measured live):
  Error rate: {stable_error:.1%}
  Average latency: {stable_latency:.0f} ms

CANARY VERSION (20% traffic, measured live):
  Error rate: {canary_error:.1%}
  Average latency: {canary_latency:.0f} ms

CALCULATED DELTAS:
  Error rate delta: {error_delta:+.1%}
  Latency delta: {latency_delta_pct:+.1f}%

DOCKER LOGS (canary container):
{docker_logs[-300:] if docker_logs else "No logs"}

Acceptable thresholds: error delta < 5%, latency increase < 30%

Decide:
- CONTINUE: metrics within acceptable range
- ROLLBACK: degradation detected

Reply with this exact JSON:
{{
  "action": "CONTINUE" or "ROLLBACK",
  "reason": "explanation with actual measured values",
  "error_delta": {error_delta:.4f},
  "latency_delta_pct": {latency_delta_pct:.1f},
  "confidence": "HIGH", "MEDIUM" or "LOW"
}}"""

    response, elapsed = ask_ollama(prompt, SYSTEM)
    parsed = parse_json_response(response)
    parsed["agent"] = "canary"
    parsed["llm_time_sec"] = elapsed
    return parsed