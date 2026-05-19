from .base_agent import ask_ollama, parse_json_response

SYSTEM = """You are a DevOps delivery agent. Analyze real CI/CD pipeline data including
test results, code coverage, security scan, and smoke tests to decide if deployment should proceed.
Reply ONLY with a JSON object, no other text."""

def analyze(data):
    gh_status = data.get("gh_actions_status", "unknown")
    tests_passed = data.get("tests_passed", 0)
    tests_failed = data.get("tests_failed", 0)
    tests_total = data.get("tests_total", 0)
    coverage_pct = data.get("coverage_pct", 0)
    security_issues = data.get("security_issues", 0)
    smoke_passed = data.get("smoke_passed", 0)
    smoke_failed = data.get("smoke_failed", 0)
    canary_error = data.get("canary_error_rate", 0)
    stable_error = data.get("stable_error_rate", 0)
    docker_logs = data.get("docker_logs", "")
    previous_incidents = data.get("previous_incidents", [])

    # Format previous incidents for context
    incidents_context = ""
    if previous_incidents:
        incidents_context = "\nPREVIOUS INCIDENTS (feedback loop):\n"
        for inc in previous_incidents:
            incidents_context += (f"  - Root cause: {inc.get('root_cause', '')}\n"
                                 f"    Prevention: {inc.get('prevent_recurrence', [])}\n")

    prompt = f"""Analyze this real CI/CD pipeline data and decide if deployment should proceed:

GITHUB ACTIONS RESULT:
  Status: {gh_status}

PYTEST TEST RESULTS:
  Passed: {tests_passed}/{tests_total}
  Failed: {tests_failed}/{tests_total}

CODE COVERAGE:
  Coverage: {coverage_pct}% (minimum acceptable: 60%)

SECURITY SCAN (Bandit):
  Issues found: {security_issues} (maximum acceptable: 2)

SMOKE TESTS (post-deploy):
  Passed: {smoke_passed}/4
  Failed: {smoke_failed}/4

LIVE METRICS:
  Stable error rate: {stable_error:.1%}
  Canary error rate: {canary_error:.1%}

DOCKER LOGS:
{docker_logs[-300:] if docker_logs else "No logs"}
{incidents_context}

Decision criteria:
- DEPLOY: GitHub Actions success AND tests pass AND smoke tests pass AND security issues <= 2
- BLOCK: GitHub Actions failure OR tests fail OR smoke tests fail OR security issues > 5

Reply with this exact JSON:
{{
  "decision": "DEPLOY" or "BLOCK",
  "risk_level": "LOW", "MEDIUM" or "HIGH",
  "reason": "explanation referencing actual pipeline results",
  "blocking_issues": ["list of issues or empty list"],
  "coverage_adequate": true or false,
  "security_acceptable": true or false
}}"""

    response, elapsed = ask_ollama(prompt, SYSTEM)
    parsed = parse_json_response(response)
    parsed["agent"] = "delivery"
    parsed["llm_time_sec"] = elapsed
    return parsed