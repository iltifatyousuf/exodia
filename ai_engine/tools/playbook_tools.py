import os
import json
import requests
from datetime import datetime, timezone
from langchain_core.tools import tool

CLOUDFLARE_API_KEY = os.getenv("CLOUDFLARE_API_KEY", "")
CLOUDFLARE_ZONE_ID = os.getenv("CLOUDFLARE_ZONE_ID", "")
PALO_ALTO_ENDPOINT = os.getenv("PALO_ALTO_ENDPOINT", "")

def log_playbook_action(action_type: str, details: dict):
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "playbook_actions.jsonl")
    
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action_type,
        "details": details
    }
    try:
        with open(log_file, "a") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception as e:
        print(f"[Error] Failed to write to playbook actions log: {e}")

@tool
def block_ip_address(ip_address: str) -> str:
    """
    [PRODUCTION] Executes a real SOAR playbook to block a malicious IP on the Cloudflare WAF.
    Requires CLOUDFLARE_API_KEY to be set in the environment.
    """
    print(f"\n[SOAR EXECUTING] Issuing API call to Cloudflare WAF to block IP {ip_address}...")
    
    log_playbook_action("block_ip", {"ip_address": ip_address})
    
    if CLOUDFLARE_API_KEY and CLOUDFLARE_ZONE_ID:
        url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/firewall/access_rules/rules"
        headers = {
            "Authorization": f"Bearer {CLOUDFLARE_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "mode": "block",
            "configuration": {
                "target": "ip",
                "value": ip_address
            },
            "notes": "Blocked automatically by Exodia AI Auto-Remediation Agent"
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            response.raise_for_status()
            return f"SUCCESS: IP {ip_address} has been actively blocked on Cloudflare WAF."
        except Exception as e:
            return f"FAILED to block IP {ip_address} on Cloudflare: {str(e)}"
            
    return f"SIMULATED SUCCESS: IP {ip_address} blocked (Cloudflare API keys not configured)."

@tool
def isolate_host(hostname: str) -> str:
    """
    [PRODUCTION] Executes a real SOAR playbook to quarantine an internal server using Palo Alto Panorama APIs.
    """
    print(f"\n[SOAR EXECUTING] Issuing API call to Palo Alto Panorama to quarantine {hostname}...")
    
    log_playbook_action("isolate_host", {"hostname": hostname})
    
    if PALO_ALTO_ENDPOINT:
        try:
            response = requests.post(f"{PALO_ALTO_ENDPOINT}/quarantine", json={"target": hostname}, timeout=5)
            response.raise_for_status()
            return f"SUCCESS: Internal host {hostname} isolated at the switch port level via Palo Alto."
        except Exception as e:
            return f"FAILED to isolate host {hostname}: {str(e)}"
            
    return f"SIMULATED SUCCESS: Host {hostname} isolated (Palo Alto endpoint not configured)."
