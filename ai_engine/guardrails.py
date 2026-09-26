import json
import os
from datetime import datetime, timezone

def evaluate_ai_confidence(ai_response: str) -> float:
    """
    Evaluates AI confidence using a weighted keyword scoring system.
    """
    weights = {
        "might": -0.1,
        "unsure": -0.2,
        "suspect": -0.1,
        "possibly": -0.1,
        "unclear": -0.2,
        "cannot confirm": -0.3,
        "portscan": -0.2,
        "unknown": -0.1,
        "error": -0.3,
        "confident": 0.1,
        "confirmed": 0.2
    }
    
    score = 1.0
    lower_resp = ai_response.lower()
    for word, weight in weights.items():
        if word in lower_resp:
            score += weight
            
    return max(min(score, 1.0), 0.0)

def send_to_human_review_queue(alert_data_str: str, ai_analysis: str):
    """
    Writes a low-confidence decision to a local human review queue.
    """
    print("\n==================================================")
    print("🚨 [GUARDRAILS TRIGGERED] LOW AI CONFIDENCE SCORE 🚨")
    print("==================================================")
    print("Routing incident to Human-in-the-Loop Review Queue...")
    
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    queue_file = os.path.join(log_dir, "human_review_queue.jsonl")
    
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "alert_data": alert_data_str,
        "ai_analysis": ai_analysis,
        "status": "pending_review"
    }
    
    try:
        with open(queue_file, "a") as f:
            f.write(json.dumps(payload) + "\n")
        print(f"[Review Queue] Incident logged to {queue_file}")
    except Exception as e:
        print(f"[Error] Failed to write to human review queue: {e}")
        
    print("Awaiting manual SOC Analyst approval before auto-remediation...")
    print("==================================================\n")
