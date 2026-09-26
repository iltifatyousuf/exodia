import socket
import threading
import json
import os
import time
from datetime import datetime
from confluent_kafka import Producer

# Configuration
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
TOPIC_NAME = os.getenv("KAFKA_TOPIC", "enriched-alerts")

# Common ports that attackers scan
HONEYPOT_PORTS = {
    22: "SSH",
    23: "Telnet",
    3306: "MySQL",
    6379: "Redis",
    8080: "HTTP-Alt"
}

print(f"[*] Initializing Kafka Producer to broker: {KAFKA_BROKER}")
producer = Producer({'bootstrap.servers': KAFKA_BROKER})

def report_to_exodia(src_ip: str, port: int, protocol: str, raw_data: bytes):
    """Fires a high-fidelity alert directly into Exodia's Kafka stream."""
    alert_id = f"HP-{int(time.time())}"
    
    payload = {
        "alert_id": alert_id,
        "type": "HONEYPOT_TRIPWIRE",
        "src_ip": src_ip,
        "dest_port": port,
        "severity": "CRITICAL",
        "description": f"Reconnaissance detected on Deception Network. Port {port} ({protocol}) accessed.",
        "payload": repr(raw_data) if raw_data else "Connection established, no payload"
    }
    
    print(f"\n🚨 [TRIPWIRE TRIGGERED] Attacker {src_ip} touched Honeypot on port {port}!")
    
    producer.produce(TOPIC_NAME, json.dumps(payload).encode('utf-8'))
    producer.poll(0)
    producer.flush()

def handle_connection(client_socket, address, port, protocol):
    """Handles the incoming connection, logs it, and closes it."""
    src_ip = address[0]
    
    try:
        # Give them a fake banner to keep them on the line for a second
        if port == 22:
            client_socket.send(b"SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.1\r\n")
        elif port == 3306:
            client_socket.send(b"5.7.31-0ubuntu0.18.04.1\n")
            
        client_socket.settimeout(3.0)
        raw_data = client_socket.recv(1024)
    except socket.timeout:
        raw_data = b""
    except Exception as e:
        raw_data = b""
    finally:
        client_socket.close()
        
    # Immediately report the attacker to the AI Brain
    report_to_exodia(src_ip, port, protocol, raw_data)

def start_listener(port, protocol):
    """Starts a socket listener on a specific honeypot port."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind(("0.0.0.0", port))
        server.listen(5)
        print(f"[*] Deception module active on port {port} ({protocol})")
        
        while True:
            client, addr = server.accept()
            # Handle the connection in a separate thread so we don't block
            client_handler = threading.Thread(target=handle_connection, args=(client, addr, port, protocol))
            client_handler.start()
            
    except PermissionError:
        print(f"[!] Permission denied: Cannot bind to port {port}. Run as Administrator/Root.")
    except Exception as e:
        print(f"[!] Error on port {port}: {e}")

def deploy_deception_network():
    """Deploys all honeypot listeners."""
    print("==================================================")
    print("   ACTIS EXODIA - DECEPTION NETWORK (HONEYPOT)")
    print("==================================================")
    
    threads = []
    for port, protocol in HONEYPOT_PORTS.items():
        t = threading.Thread(target=start_listener, args=(port, protocol))
        t.daemon = True
        t.start()
        threads.append(t)
        
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Shutting down Deception Network...")

if __name__ == "__main__":
    deploy_deception_network()
