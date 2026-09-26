import os
import json
import requests
from datetime import datetime, timezone

# SIEM Configuration
SPLUNK_HEC_URL = os.getenv("SPLUNK_HEC_URL", "")
SPLUNK_HEC_TOKEN = os.getenv("SPLUNK_HEC_TOKEN", "")
ELASTIC_URL = os.getenv("ELASTIC_URL", "")

def forward_to_siem(alert_id: str, threat_data: dict, ai_analysis: str, soar_action: str):
    """
    [PRODUCTION] Forwards the complete Threat Intelligence payload, AI reasoning, 
    and SOAR remediation action to the Enterprise SIEM (Splunk/Elasticsearch) 
    and logs locally.
    """
    print(f"\n[SIEM FORWARDER] Dispatching Incident {alert_id}...")
    
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "incident_id": alert_id,
        "source": "Exodia LangGraph AI Orchestrator",
        "threat_telemetry": threat_data,
        "ai_verdict": ai_analysis,
        "remediation_taken": soar_action,
        "compliance_status": "SOC2 CC6.1 - Automated Remediation Logged"
    }

    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    audit_file = os.path.join(log_dir, "siem_audit.jsonl")
    
    try:
        with open(audit_file, "a") as f:
            f.write(json.dumps(payload) + "\n")
        print(f"[SIEM FORWARDER] Successfully wrote to local audit log.")
    except Exception as e:
        print(f"[Error] Failed to write to local audit log: {e}")

    if SPLUNK_HEC_URL and SPLUNK_HEC_TOKEN:
        splunk_headers = {"Authorization": f"Splunk {SPLUNK_HEC_TOKEN}"}
        splunk_payload = {"event": payload, "sourcetype": "_json"}
        try:
            requests.post(SPLUNK_HEC_URL, headers=splunk_headers, json=splunk_payload, verify=False, timeout=3)
            print("[SIEM FORWARDER] Forwarded to Splunk.")
        except Exception as e:
            print(f"[Warning] Failed to forward to Splunk: {e}")

    if ELASTIC_URL:
        try:
            requests.post(ELASTIC_URL, json=payload, timeout=3)
            print("[SIEM FORWARDER] Forwarded to Elasticsearch.")
        except Exception as e:
            print(f"[Warning] Failed to forward to Elasticsearch: {e}")
