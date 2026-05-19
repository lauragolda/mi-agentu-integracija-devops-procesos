from .base_agent import ask_ollama, parse_json_response

SYSTEM = """You are a DevOps monitoring and diagnostics agent. Analyze real metrics 
and actual Docker container logs to identify incidents and recommend actions.
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

    # Sanem canary agenta lemumu (kede)
    canary_result = data.get("canary_agent_result", {})
    canary_action = canary_result.get("action", "")
    canary_confidence = canary_result.get("confidence", "")
    monitoring_result = data.get("monitoring_result", {})

    canary_context = ""
    if canary_action:
        canary_context = f"""
CANARY DEPLOYMENT AGENT DECISION (previous agent in chain):
  Action: {canary_action}
  Confidence: {canary_confidence}
  Error delta: {canary_result.get('error_delta', 0):.4f}
  Latency delta: {canary_result.get('latency_delta_pct', 0):.1f}%
  Note: If canary agent says CONTINUE with HIGH confidence, 
  only report INCIDENT if you see CLEAR error patterns in logs.
"""

    monitoring_context = ""
    if monitoring_result:
        monitoring_context = f"""
MONITORING AGENT REPORT (previous agent in chain):
  Status: {monitoring_result.get('status', '')}
  Action: {monitoring_result.get('action', '')}
  Root cause: {monitoring_result.get('root_cause', '')}
"""

    prompt = f"""Post-deployment monitoring based on REAL container data:

GITHUB ACTIONS STATUS: {gh_status}

LIVE METRICS:
  Stable version - error rate: {stable_error:.1%}, latency: {stable_latency:.0f}ms
  New version - error rate: {canary_error:.1%}, latency: {canary_latency:.0f}ms
  Error delta: {error_delta:+.1%}
  Latency delta: {latency_delta_pct:+.1f}%
{canary_context}{monitoring_context}
ACTUAL DOCKER LOGS (new version container):
{docker_logs if docker_logs else "No logs available"}

DECISION CRITERIA:
  - STABLE / NONE: metrics normal (error delta < 5%, latency delta < 30%) 
    AND no error patterns in logs
  - INCIDENT / INVESTIGATE: some anomalies detected but unclear
  - INCIDENT / ROLLBACK: clear errors in logs OR significant metric degradation

Reply with this exact JSON:
{{
  "status": "STABLE" or "INCIDENT",
  "action": "NONE", "ROLLBACK" or "INVESTIGATE",
  "root_cause": "identified cause from logs and metrics, or 'no anomalies detected'",
  "summary": "2-3 sentence summary of system state",
  "recommended_steps": ["concrete action steps"]
}}"""

    response, elapsed = ask_ollama(prompt, SYSTEM)
    parsed = parse_json_response(response)
    parsed["agent"] = "monitoring"
    parsed["llm_time_sec"] = elapsed
    return parsed