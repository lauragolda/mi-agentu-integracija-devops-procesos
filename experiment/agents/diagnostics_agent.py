from .base_agent import ask_ollama, parse_json_response

SYSTEM = """You are a DevOps diagnostics agent. You receive incident data from the 
monitoring agent and perform deep root cause analysis. 
Reply ONLY with a JSON object, no other text."""

def analyze(data, monitoring_result=None):
    canary_error = data.get("canary_error_rate", 0)
    stable_error = data.get("stable_error_rate", 0)
    canary_latency = data.get("canary_latency_ms", 0)
    stable_latency = data.get("stable_latency_ms", 0)
    docker_logs = data.get("docker_logs", "")

    # Saņem uzraudzības aģenta JSON (ķēde)
    prev_context = ""
    if monitoring_result:
        prev_context = f"""
MONITORING AGENT REPORT (previous agent in chain):
  Status: {monitoring_result.get("status", "unknown")}
  Action: {monitoring_result.get("action", "unknown")}
  Initial root cause: {monitoring_result.get("root_cause", "unknown")}
  Summary: {monitoring_result.get("summary", "")}
  Recommended steps: {monitoring_result.get("recommended_steps", [])}
"""

    prompt = f"""You are performing deep root cause analysis of a production incident.
{prev_context}
LIVE METRICS AT TIME OF INCIDENT:
  Stable version - error rate: {stable_error:.1%}, latency: {stable_latency:.0f}ms
  Failing version - error rate: {canary_error:.1%}, latency: {canary_latency:.0f}ms
  Error delta: {canary_error - stable_error:+.1%}
  Latency delta: {(canary_latency - stable_latency) / max(stable_latency, 1) * 100:+.1f}%

DOCKER LOGS (full analysis):
{docker_logs if docker_logs else "No logs available"}

Perform deep root cause analysis and provide recovery plan.

Reply with this exact JSON:
{{
  "action": "ROLLBACK" or "INVESTIGATE",
  "root_cause": "detailed root cause identified from logs and metrics",
  "impact_assessment": "how many users affected and severity",
  "recovery_steps": ["step 1", "step 2", "step 3"],
  "summary": "3 sentence incident report for the development team",
  "prevent_recurrence": ["recommendation 1", "recommendation 2"]
}}"""

    response, elapsed = ask_ollama(prompt, SYSTEM)
    parsed = parse_json_response(response)
    parsed["agent"] = "diagnostics"
    parsed["llm_time_sec"] = elapsed
    return parsed