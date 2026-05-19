import csv, os, time, requests, subprocess, sys, json, zipfile, io, re, threading

env = {}
with open(r'C:\Users\TAAGOLA6\bakalaurs-experiment\.env', 'r') as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            key, val = line.split('=', 1)
            env[key.strip()] = val.strip()

GITHUB_TOKEN = env.get("GITHUB_TOKEN", "")
GITHUB_REPO = env.get("GITHUB_REPO", "")
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

REPO_DIR = r'C:\Users\TAAGOLA6\bakalaurs-experiment'
OUTPUT_FILE = "results/results.csv"
STABLE_URL = "http://localhost:5000"
CANARY_URL = "http://localhost:5001"
NGINX_URL = "http://localhost:8080"
FEEDBACK_FILE = "results/feedback_loop.json"

FIELDNAMES = [
    "scenario_id", "run_id",
    "decision", "reason", "correct",
    "time_sec", "llm_time_sec",
    "tests_passed", "tests_failed", "tests_total",
    "canary_error_rate", "canary_latency_ms",
    "stable_error_rate", "stable_latency_ms",
    "nginx_error_rate", "nginx_latency_ms",
    "gh_actions_status", "docker_logs",
    "canary_version", "log_lines", "log_chars"
]

SCENARIOS = {
    "S1": {"branch": "stable",  "runs": 10, "expect": "DEPLOY",   "canary": "stable"},
    "S2": {"branch": "broken",  "runs": 10, "expect": "BLOCK",    "canary": "broken_tests"},
    "S3": {"branch": "stable",  "runs": 10, "expect": "CONTINUE", "canary": "stable"},
    "S4": {"branch": "broken",  "runs": 10, "expect": "ROLLBACK", "canary": "broken_latency"},
    "S5": {"branch": "stable",  "runs": 10, "expect": "STABLE",   "canary": "stable"},
    "S6": {"branch": "broken",  "runs": 10, "expect": "ROLLBACK", "canary": "broken_memory"},
    "S7": {"branch": "stable",  "runs": 10, "expect": "ROLLBACK", "canary": "broken_edge"},
}

def git_cmd(args):
    return subprocess.run(
        ["git"] + args,
        capture_output=True, text=True, cwd=REPO_DIR
    )

def switch_canary(version):
    print(f"  [Canary] Rebuilding canary with {version}...")
    context = os.path.join(REPO_DIR, "app", version)
    subprocess.run(
        ["docker", "build", "-t", f"app-canary-{version}", context],
        capture_output=True, cwd=REPO_DIR
    )
    subprocess.run(["docker", "rm", "-f", "app-canary"], capture_output=True)
    version_map = {
        "stable":           "1.1.0",
        "broken_tests":     "2.1.0",
        "broken_latency":   "2.2.0",
        "broken_memory":    "2.3.0",
        "broken_edge":      "2.4.0",
        "broken_security":  "2.5.0",
    }
    subprocess.run([
        "docker", "run", "-d",
        "--name", "app-canary",
        "--network", "bakalaurs-experiment_default",
        "-p", "5001:5000",
        "-e", f"APP_VERSION={version_map.get(version, '2.0.0')}",
        f"app-canary-{version}"
    ], capture_output=True)
    time.sleep(3)
    print(f"[Canary] Done - canary is now {version}")

def save_feedback(scenario_id, run_id, diag_result):
    feedback = {
        "from_scenario": scenario_id,
        "run_id": run_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "root_cause": diag_result.get("root_cause", ""),
        "recovery_steps": diag_result.get("recovery_steps", []),
        "prevent_recurrence": diag_result.get("prevent_recurrence", []),
    }
    existing = []
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "r") as f:
            try:
                existing = json.load(f)
            except:
                existing = []
    existing.append(feedback)
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(existing, f, indent=2)
    print(f"[Feedback] Saved diagnostics to feedback loop")

def load_feedback():
    if not os.path.exists(FEEDBACK_FILE):
        return []
    with open(FEEDBACK_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return []

def trigger_github_actions(branch):
    print(f"[CI] Triggering GitHub Actions on branch: {branch}...")
    git_cmd(["checkout", branch])
    git_cmd(["commit", "--allow-empty", "-m", "CI trigger: experiment run"])
    git_cmd(["push", "origin", branch])
    git_cmd(["checkout", "main"])
    time.sleep(5)

def wait_for_actions_result(branch, timeout=300):
    print(f"[CI] Waiting for GitHub Actions ({branch})...")
    start = time.time()
    last_run_id = None
    while time.time() - start < timeout:
        try:
            r = requests.get(
                f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs"
                f"?branch={branch}&per_page=1",
                headers=HEADERS, timeout=10
            )
            runs = r.json().get("workflow_runs", [])
            if not runs:
                time.sleep(5)
                continue
            run = runs[0]
            run_id = run["id"]
            status = run["status"]
            conclusion = run["conclusion"]
            if last_run_id != run_id:
                last_run_id = run_id
            if status == "completed":
                print(f"  [CI] Result: {conclusion}")
                return run_id, conclusion
            print(f"  [CI] Status: {status}... waiting")
        except Exception as e:
            print(f"  [CI] API error: {e}")
        time.sleep(10)
    return None, "timeout"

def get_test_results_from_actions(run_id):
    if not run_id:
        return 0, 0, 0, "", 0, 0
    try:
        r = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs/{run_id}/jobs",
            headers=HEADERS, timeout=10
        )
        jobs = r.json().get("jobs", [])
        output = ""
        for job in jobs:
            for step in job.get("steps", []):
                output += f"Step '{step.get('name')}': {step.get('conclusion')}\n"

        logs_r = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs/{run_id}/logs",
            headers=HEADERS, timeout=30, allow_redirects=True
        )

        passed = 0
        failed = 0
        coverage = 0
        security_issues = 0
        full_text = ""

        if logs_r.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(logs_r.content)) as z:
                for name in z.namelist():
                    with z.open(name) as f:
                        full_text += f.read().decode("utf-8", errors="ignore")

            match = re.search(r'(\d+) failed[,\s]+(\d+) passed', full_text)
            if match:
                failed = int(match.group(1))
                passed = int(match.group(2))
            else:
                match2 = re.search(r'(\d+) passed', full_text)
                if match2:
                    passed = int(match2.group(1))

            cov_match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', full_text)
            if cov_match:
                coverage = int(cov_match.group(1))

            sec_json = re.findall(r'"issue_text":', full_text)
            if sec_json:
                security_issues = len(sec_json)
            else:
                sec_issues = re.findall(r'>> Issue:', full_text)
                security_issues = len(sec_issues)

        return passed, failed, passed + failed, output, coverage, security_issues

    except Exception as e:
        print(f"  [CI] Logs error: {e}")
        return 0, 0, 0, "", 0, 0

def generate_load(url, count, results):
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
    results["error_rate"] = round(errors / count, 4)
    results["avg_latency"] = round(sum(latencies) / len(latencies), 1)

def measure_with_load(count=100):
    nginx_r = {}
    stable_r = {}
    canary_r = {}
    threads = [
        threading.Thread(target=generate_load, args=(NGINX_URL, count, nginx_r)),
        threading.Thread(target=generate_load, args=(STABLE_URL, count // 2, stable_r)),
        threading.Thread(target=generate_load, args=(CANARY_URL, count // 2, canary_r)),
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    print(f" [Load] Nginx: errors={nginx_r.get('error_rate',0):.0%}, "
          f"latency={nginx_r.get('avg_latency',0):.0f}ms")
    print(f" [Load] Stable: errors={stable_r.get('error_rate',0):.0%}, "
          f"latency={stable_r.get('avg_latency',0):.0f}ms")
    print(f" [Load] Canary: errors={canary_r.get('error_rate',0):.0%}, "
          f"latency={canary_r.get('avg_latency',0):.0f}ms")

    return {
        "nginx_error_rate": nginx_r.get("error_rate", 0),
        "nginx_latency_ms": nginx_r.get("avg_latency", 0),
        "stable_error_rate": stable_r.get("error_rate", 0),
        "stable_latency_ms": stable_r.get("avg_latency", 0),
        "canary_error_rate": canary_r.get("error_rate", 0),
        "canary_latency_ms": canary_r.get("avg_latency", 0),
    }

def get_docker_logs(container, lines=30):
    try:
        r = subprocess.run(
            ["docker", "logs", "--tail", str(lines), container],
            capture_output=True, text=True
        )
        return (r.stdout + r.stderr).strip()
    except:
        return ""

def do_rollback():
    print("[ROLLBACK] Switching canary back to stable...")
    subprocess.run(["docker", "rm", "-f", "app-canary"], capture_output=True)
    subprocess.run([
        "docker", "run", "-d",
        "--name", "app-canary",
        "--network", "bakalaurs-experiment_default",
        "-p", "5001:5000",
        "-e", "APP_VERSION=1.0.0-rollback",
        "app-canary-stable"
    ], capture_output=True)
    time.sleep(3)
    success = 0
    for _ in range(5):
        try:
            r = requests.get(f"{CANARY_URL}/health", timeout=5)
            if r.status_code == 200:
                success += 1
        except:
            pass
    if success >= 4:
        print(f"[ROLLBACK] SUCCESS - system stable ({success}/5 checks passed)")
    else:
        print(f"[ROLLBACK] WARNING - unstable ({success}/5 checks passed)")
    return success >= 4

def run_all():
    os.makedirs("results", exist_ok=True)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from p2_engine import run_p2

    total = sum(v["runs"] for v in SCENARIOS.values())
    done = 0

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

        for scenario_id, cfg in SCENARIOS.items():
            branch = cfg["branch"]
            runs = cfg["runs"]
            canary_version = cfg["canary"]

            print(f"\n{'='*55}")
            print(f"SCENARIO: {scenario_id} | Branch: {branch} | "
                  f"Canary: {canary_version} | {runs} runs")
            print(f"{'='*55}")

            for run_id in range(1, runs + 1):
                done += 1
                print(f"\n[{done}/{total}] {scenario_id} - run {run_id}")

                switch_canary(canary_version)
                trigger_github_actions(branch)
                gh_run_id, gh_conclusion = wait_for_actions_result(branch)

                passed, failed, total_tests, test_output, coverage, security = \
                    get_test_results_from_actions(gh_run_id)
                print(f"Tests: {passed} passed / {failed} failed | "
                      f"Coverage: {coverage}% | Security: {security}")

                print("[Load] Generating load...")
                load_metrics = measure_with_load(100)

                docker_logs = get_docker_logs("app-canary")
                log_lines = len(docker_logs.splitlines())
                log_chars = len(docker_logs)
                print(f"[Logs] {log_lines} lines, {log_chars} chars")

                previous_feedback = load_feedback()

                pipeline_data = {
                    "scenario_id": scenario_id,
                    "run_id": run_id,
                    "canary_version": canary_version,
                    "gh_actions_status": gh_conclusion or "unknown",
                    "tests_passed": passed,
                    "tests_failed": failed,
                    "tests_total": total_tests,
                    "test_output": test_output,
                    "coverage_pct": coverage,
                    "security_issues": security,
                    "canary_error_rate": load_metrics["canary_error_rate"],
                    "canary_latency_ms": load_metrics["canary_latency_ms"],
                    "stable_error_rate": load_metrics["stable_error_rate"],
                    "stable_latency_ms": load_metrics["stable_latency_ms"],
                    "nginx_error_rate": load_metrics["nginx_error_rate"],
                    "nginx_latency_ms": load_metrics["nginx_latency_ms"],
                    "docker_logs": docker_logs,
                    "previous_incidents": previous_feedback[-3:] if previous_feedback else [],
                }

                result = run_p2(pipeline_data)

                writer.writerow({
                    "scenario_id": scenario_id,
                    "run_id": run_id,
                    "decision": result["decision"],
                    "reason": result["reason"],
                    "correct": result["correct"],
                    "time_sec": result["time_sec"],
                    "llm_time_sec": result["llm_time_sec"],
                    "tests_passed": passed,
                    "tests_failed": failed,
                    "tests_total": total_tests,
                    "canary_error_rate": load_metrics["canary_error_rate"],
                    "canary_latency_ms": load_metrics["canary_latency_ms"],
                    "stable_error_rate": load_metrics["stable_error_rate"],
                    "stable_latency_ms": load_metrics["stable_latency_ms"],
                    "nginx_error_rate": load_metrics["nginx_error_rate"],
                    "nginx_latency_ms": load_metrics["nginx_latency_ms"],
                    "gh_actions_status": gh_conclusion,
                    "docker_logs": docker_logs[:200],
                    "canary_version": canary_version,
                    "log_lines": log_lines,
                    "log_chars": log_chars,
                })
                f.flush()
                print(f"Decision: {result['decision']} "
                      f"({'CORRECT' if result['correct'] else 'WRONG'}) "
                      f"[{result['llm_time_sec']:.1f}s]")

                if result["decision"] in ["ROLLBACK", "BLOCK"]:
                    do_rollback()

                if scenario_id == "S6":
                    try:
                        chain = eval(result.get("chain_log", "[]"))
                        for entry in chain:
                            if entry.get("agent") == "diagnostics":
                                save_feedback(scenario_id, run_id, entry)
                    except:
                        pass

    print(f"\nResults saved: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_all()
