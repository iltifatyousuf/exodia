import os
import json
import time
import random
from confluent_kafka import Producer

# Configuration
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
TOPIC_NAME = os.getenv("KAFKA_TOPIC", "enriched-alerts")

# Mock Attack Scenarios
SCENARIOS = [
    {
        "alert_id": "INC-8001",
        "type": "SQL_INJECTION",
        "src_ip": "203.0.113.45",
        "dest_ip": "10.0.0.15",
        "severity": "HIGH",
        "payload": "'; DROP TABLE users; --",
        "description": "Standard SQL injection attempt detected in HTTP POST body."
    },
    {
        "alert_id": "INC-8002",
        "type": "DATA_EXFILTRATION",
        "src_ip": "10.0.0.88",
        "dest_ip": "198.51.100.22",
        "severity": "MEDIUM",
        "payload": "Encrypted tunnel (Port 443)",
        "description": "Unusual outbound data spike (4.2 GB) from internal database server at 3:00 AM."
    },
    {
        "alert_id": "INC-8003",
        "type": "SSH_BRUTE_FORCE",
        "src_ip": "198.51.100.99",
        "dest_ip": "10.0.0.5",
        "severity": "HIGH",
        "payload": "root:password123",
        "description": "500 failed SSH login attempts in 10 seconds."
    }
]

def delivery_report(err, msg):
    """Called once for each message produced to indicate delivery result."""
    if err is not None:
        print(f"[Simulator Error] Message delivery failed: {err}")
    else:
        print(f"[Simulator] Sent mock telemetry to {msg.topic()} [{msg.partition()}]")

def run_simulator():
    """Continuously fires mock alerts into the Kafka stream."""
    print("==================================================")
    print("   EXODIA CHAOS ENGINEERING - THREAT SIMULATOR")
    print("==================================================")
    print(f"[*] Connecting to Kafka broker at {KAFKA_BROKER}")
    
    producer = Producer({'bootstrap.servers': KAFKA_BROKER})
    
    try:
        while True:
            # Pick a random attack scenario
            scenario = random.choice(SCENARIOS)
            
            # Slightly modify the alert ID and IP for uniqueness on repeat loops
            scenario["alert_id"] = f"INC-{random.randint(9000, 9999)}"
            
            # If it's a brute force, occasionally keep the same IP to test the Redis hot-cache
            if scenario["type"] != "SSH_BRUTE_FORCE":
                scenario["src_ip"] = f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"

            print(f"\n[+] Firing simulated attack: {scenario['type']} from {scenario['src_ip']}")
            
            # Push to Kafka
            producer.produce(
                TOPIC_NAME, 
                json.dumps(scenario).encode('utf-8'), 
                callback=delivery_report
            )
            producer.poll(0)
            
            # Wait 10-15 seconds before the next attack
            sleep_time = random.randint(10, 15)
            print(f"[*] Sleeping for {sleep_time} seconds...")
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n[*] Shutting down simulator...")
    finally:
        producer.flush()

if __name__ == "__main__":
    run_simulator()
