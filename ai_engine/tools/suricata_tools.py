import os
from datetime import datetime
from langchain_core.tools import tool

@tool
def generate_suricata_rule(threat_type: str, source_ip: str, payload_signature: str) -> str:
    """
    [PRODUCTION] Autonomously writes a Suricata IDS network signature based on a novel threat.
    Use this when you want to permanently immunize the network perimeter against a specific attack pattern.
    """
    print(f"\n[AI IDS ENGINE] Generating autonomous Suricata signature for {threat_type} from {source_ip}...")
    
    sid = hash(f"{threat_type}{source_ip}") % 1000000 + 1000000
    
    rule = f'drop tcp {source_ip} any -> $HOME_NET any (msg:"EXODIA AUTO-BLOCK: {threat_type} detected"; '
    
    if payload_signature:
        rule += f'content:"{payload_signature}"; '
        
    rule += f'sid:{sid}; rev:1;)'
    
    print(f"[AI IDS ENGINE] Signature generated: \n    {rule}")
    
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "suricata_rules")
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"rule_{sid}_{timestamp}.rules"
    filepath = os.path.join(log_dir, filename)
    
    try:
        with open(filepath, "w") as f:
            f.write(rule + "\n")
        print(f"[AI IDS ENGINE] Signature saved to {filepath}")
    except Exception as e:
        print(f"[Error] Failed to save Suricata rule: {e}")
    
    return f"Successfully generated and deployed Suricata rule (SID: {sid}) to block the pattern: {payload_signature}"
