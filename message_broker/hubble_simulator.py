import json
import time
import random
from confluent_kafka import Producer

KAFKA_BROKER = 'localhost:9092'
TOPIC_NAME = 'network-alerts'

def delivery_report(err, msg):
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"[*] Sent packet alert to Kafka: {msg.topic()} [{msg.partition()}]")

def simulate_hubble_traffic():
    p = Producer({'bootstrap.servers': KAFKA_BROKER})
    
    print(f"Starting Hubble eBPF Packet Simulator. Sending to {KAFKA_BROKER}...")
    
    anomalies = [
        {"alert_id": "EVT-001", "type": "PortScan", "source_ip": "192.168.1.45", "target_port": 22, "severity": "Medium"},
        {"alert_id": "EVT-002", "type": "MassDataExfiltration", "source_ip": "10.0.0.12", "bytes_sent": 5000000000, "severity": "Critical"},
        {"alert_id": "EVT-003", "type": "SQLInjection_Attempt", "source_ip": "203.0.113.5", "payload": "DROP TABLE users;", "severity": "High"}
    ]
    
    for anomaly in anomalies:
        time.sleep(2)  # Simulate time between events
        
        # Send data to Kafka
        p.produce(
            TOPIC_NAME, 
            json.dumps(anomaly).encode('utf-8'), 
            callback=delivery_report
        )
        p.poll(0)
        
    p.flush()
    print("Simulation complete.")

if __name__ == "__main__":
    simulate_hubble_traffic()
