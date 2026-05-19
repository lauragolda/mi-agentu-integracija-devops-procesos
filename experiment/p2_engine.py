import time
from agents import delivery_agent, infra_agent, canary_agent, monitoring_agent, diagnostics_agent

def run_p2(data):
    start = time.time()
    scenario_id = data["scenario_id"]
    decision = None
    reason = ""
    correct = False
    llm_total_time = 0.0
    chain_log = []

    if scenario_id in ["S1", "S2"]:
        # Agent 1: Delivery agent
        print("    [Chain 1/2] Delivery agent...")
        delivery_result = delivery_agent.analyze(data)
        llm_total_time += delivery_result.get("llm_time_sec", 0)
        chain_log.append({
            "agent": "delivery",
            "decision": delivery_result.get("decision"),
            "risk_level": delivery_result.get("risk_level"),
            "reason": delivery_result.get("reason"),
        })
        print(f"    -> Delivery: {delivery_result.get('decision')} "
              f"(risk: {delivery_result.get('risk_level')})")

        # Agent 2: Infrastructure agent (receives delivery JSON)
        print("    [Chain 2/2] Infrastructure agent...")
        infra_result = infra_agent.analyze(data, delivery_result=delivery_result)
        llm_total_time += infra_result.get("llm_time_sec", 0)
        chain_log.append({
            "agent": "infra",
            "ready": infra_result.get("ready"),
            "resource_status": infra_result.get("resource_status"),
            "reason": infra_result.get("reason"),
        })
        print(f"    -> Infra: ready={infra_result.get('ready')} "
              f"({infra_result.get('resource_status')})")

        if delivery_result.get("decision") == "BLOCK":
            decision = "BLOCK"
            reason = f"[Delivery agent] {delivery_result.get('reason', '')}"
        elif not infra_result.get("ready", True):
            decision = "BLOCK"
            reason = f"[Infra agent] {infra_result.get('reason', '')}"
        else:
            decision = "DEPLOY"
            reason = f"[Chain OK] {delivery_result.get('reason', '')}"

        correct = (decision == "DEPLOY") if scenario_id == "S1" else (decision == "BLOCK")

    elif scenario_id in ["S3", "S4"]:
        # Agent 3: Canary deployment agent
        print("    [Chain 1/2] Canary deployment agent...")
        canary_result = canary_agent.analyze(data)
        llm_total_time += canary_result.get("llm_time_sec", 0)
        chain_log.append({
            "agent": "canary",
            "action": canary_result.get("action"),
            "confidence": canary_result.get("confidence"),
            "error_delta": canary_result.get("error_delta"),
            "latency_delta_pct": canary_result.get("latency_delta_pct"),
        })
        print(f"    -> Canary: {canary_result.get('action')} "
              f"(confidence: {canary_result.get('confidence')})")

        # Agent 4: Monitoring agent (receives canary JSON)
        print("    [Chain 2/2] Monitoring agent...")
        data_with_canary = {**data, "canary_agent_result": canary_result}
        monitoring_result = monitoring_agent.analyze(data_with_canary)
        llm_total_time += monitoring_result.get("llm_time_sec", 0)
        chain_log.append({
            "agent": "monitoring",
            "status": monitoring_result.get("status"),
            "action": monitoring_result.get("action"),
            "root_cause": monitoring_result.get("root_cause"),
        })
        print(f"    -> Monitoring: {monitoring_result.get('status')} "
              f"/ {monitoring_result.get('action')}")

        canary_action = canary_result.get("action", "CONTINUE")
        monitoring_action = monitoring_result.get("action", "NONE")

        if canary_action == "ROLLBACK" or monitoring_action == "ROLLBACK":
            decision = "ROLLBACK"
            reason = (f"[Canary: {canary_action}] {canary_result.get('reason', '')} | "
                      f"[Monitoring: {monitoring_action}]")
        else:
            decision = "CONTINUE"
            reason = (f"[Chain OK] Canary: {canary_action}, "
                      f"Monitoring: {monitoring_action}")

        correct = (decision == "CONTINUE") if scenario_id == "S3" else (decision == "ROLLBACK")

    elif scenario_id == "S5":
        # Agent 4: Monitoring agent
        print("    [Chain 1/1] Monitoring agent...")
        monitoring_result = monitoring_agent.analyze(data)
        llm_total_time += monitoring_result.get("llm_time_sec", 0)
        chain_log.append({
            "agent": "monitoring",
            "status": monitoring_result.get("status"),
            "action": monitoring_result.get("action"),
        })
        print(f"    -> Monitoring: {monitoring_result.get('status')}")

        decision = monitoring_result.get("status", "STABLE")
        reason = monitoring_result.get("summary", "")
        correct = (decision == "STABLE")

    elif scenario_id == "S6":
        # Agent 4: Monitoring agent
        print("    [Chain 1/2] Monitoring agent...")
        monitoring_result = monitoring_agent.analyze(data)
        llm_total_time += monitoring_result.get("llm_time_sec", 0)
        chain_log.append({
            "agent": "monitoring",
            "status": monitoring_result.get("status"),
            "action": monitoring_result.get("action"),
            "root_cause": monitoring_result.get("root_cause"),
        })
        print(f"    -> Monitoring: {monitoring_result.get('status')} "
              f"/ {monitoring_result.get('action')}")

        # Agent 5: Diagnostics agent (receives monitoring JSON)
        print("    [Chain 2/2] Diagnostics agent...")
        diag_result = diagnostics_agent.analyze(data, monitoring_result=monitoring_result)
        llm_total_time += diag_result.get("llm_time_sec", 0)
        chain_log.append({
            "agent": "diagnostics",
            "action": diag_result.get("action"),
            "root_cause": diag_result.get("root_cause"),
            "recovery_steps": diag_result.get("recovery_steps"),
        })
        print(f"    -> Diagnostics: {diag_result.get('action')} "
              f"| Root cause: {str(diag_result.get('root_cause', ''))[:50]}")

        decision = diag_result.get("action", "ROLLBACK")
        reason = f"[Monitoring->Diagnostics] {diag_result.get('summary', '')}"
        correct = (decision in ["ROLLBACK", "INVESTIGATE"])

    elif scenario_id == "S7":
        # Canary edge case - sagaidams ROLLBACK
        print("    [Chain 1/2] Canary deployment agent...")
        canary_result = canary_agent.analyze(data)
        llm_total_time += canary_result.get("llm_time_sec", 0)
        chain_log.append({
            "agent": "canary",
            "action": canary_result.get("action"),
            "confidence": canary_result.get("confidence"),
            "error_delta": canary_result.get("error_delta"),
        })
        print(f"    -> Canary: {canary_result.get('action')} "
              f"(confidence: {canary_result.get('confidence')})")

        print("    [Chain 2/2] Monitoring agent...")
        data_with_canary = {**data, "canary_agent_result": canary_result}
        monitoring_result = monitoring_agent.analyze(data_with_canary)
        llm_total_time += monitoring_result.get("llm_time_sec", 0)
        chain_log.append({
            "agent": "monitoring",
            "status": monitoring_result.get("status"),
            "action": monitoring_result.get("action"),
        })
        print(f"    -> Monitoring: {monitoring_result.get('status')} "
              f"/ {monitoring_result.get('action')}")

        canary_action = canary_result.get("action", "CONTINUE")
        monitoring_action = monitoring_result.get("action", "NONE")

        if canary_action == "ROLLBACK" or monitoring_action == "ROLLBACK":
            decision = "ROLLBACK"
            reason = f"[Canary: {canary_action}] {canary_result.get('reason', '')}"
        else:
            decision = "CONTINUE"
            reason = f"[Chain OK] Canary: {canary_action}"

        correct = (decision == "ROLLBACK")

    elif scenario_id == "S8":
        # Security issues - sagaidams BLOCK
        print("    [Chain 1/2] Delivery agent...")
        delivery_result = delivery_agent.analyze(data)
        llm_total_time += delivery_result.get("llm_time_sec", 0)
        chain_log.append({
            "agent": "delivery",
            "decision": delivery_result.get("decision"),
            "risk_level": delivery_result.get("risk_level"),
            "reason": delivery_result.get("reason"),
        })
        print(f"    -> Delivery: {delivery_result.get('decision')} "
              f"(risk: {delivery_result.get('risk_level')})")

        print("    [Chain 2/2] Infrastructure agent...")
        infra_result = infra_agent.analyze(data, delivery_result=delivery_result)
        llm_total_time += infra_result.get("llm_time_sec", 0)
        chain_log.append({
            "agent": "infra",
            "ready": infra_result.get("ready"),
            "resource_status": infra_result.get("resource_status"),
        })
        print(f"    -> Infra: ready={infra_result.get('ready')} "
              f"({infra_result.get('resource_status')})")

        if delivery_result.get("decision") == "BLOCK":
            decision = "BLOCK"
            reason = f"[Delivery agent] {delivery_result.get('reason', '')}"
        elif not infra_result.get("ready", True):
            decision = "BLOCK"
            reason = f"[Infra agent] {infra_result.get('reason', '')}"
        else:
            decision = "DEPLOY"
            reason = f"[Chain OK] {delivery_result.get('reason', '')}"

        correct = (decision == "BLOCK")

    elapsed = time.time() - start
    agents_used = [s["agent"] for s in chain_log]
    print(f"    [Chain complete] Agents: {agents_used} | Total LLM time: {llm_total_time:.1f}s")

    return {
        "decision": decision,
        "reason": reason,
        "correct": correct,
        "time_sec": round(elapsed, 4),
        "llm_time_sec": round(llm_total_time, 4),
        "chain_log": str(chain_log),
    }