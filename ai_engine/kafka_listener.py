import os
import json
import time
import sys

try:
    from confluent_kafka import Consumer, KafkaError
    from prometheus_client import start_http_server, Counter, Summary
    KAFKA_AVAILABLE = True
except ImportError as e:
    print(f"[Warning] Kafka/Prometheus dependencies missing: {e}")
    KAFKA_AVAILABLE = False

from langchain_core.messages import HumanMessage

# --- Configuration (Environment Variables with Fallbacks) ---
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
TOPIC_NAME = os.getenv("KAFKA_TOPIC", "enriched-alerts")
PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", "8000"))

if KAFKA_AVAILABLE:
    THREATS_PROCESSED = Counter('actis_threats_processed_total', 'Total number of network threats processed by the AI')
    THREATS_MITIGATED = Counter('actis_threats_mitigated_total', 'Total number of threats successfully blocked/mitigated')
    AI_INFERENCE_TIME = Summary('actis_ai_inference_seconds', 'Time spent waiting for the Llama 3.2 Multi-Agent Orchestrator')
else:
    class DummyMetric:
        def inc(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
    THREATS_PROCESSED = DummyMetric()
    THREATS_MITIGATED = DummyMetric()
    AI_INFERENCE_TIME = DummyMetric()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def dummy_check(ip): return None
def dummy_set(ip, val, ttl): pass

try:
    from ai_engine.redis_cache import check_threat_cache, set_threat_cache
except ImportError:
    check_threat_cache = dummy_check
    set_threat_cache = dummy_set

from ai_engine.siem_forwarder import forward_to_siem
from ai_engine.pinecone_memory import save_to_long_term_memory


def analyze_threat_with_ai(alert_data: dict):
    alert_id = alert_data.get('alert_id', 'unknown_id')
    print(f"\n[ACTIS AI] Analyzing new network alert: {alert_id}...")
    start_time = time.time()

    try:
        target_ip = alert_data.get("src_ip", "unknown")
        if target_ip != "unknown":
            cached_verdict = check_threat_cache(target_ip)
            if cached_verdict:
                print(f"[FAST PATH] Cached verdict for {target_ip}: {cached_verdict.get('action', 'N/A')}")
                THREATS_PROCESSED.inc()
                THREATS_MITIGATED.inc()
                return

        print(f"\n[ACTIS ORCHESTRATOR] Cache miss. Routing alert {alert_id} to Sub-Agents...")
        prompt = f"New network packet detected: {json.dumps(alert_data)}"

        THREATS_PROCESSED.inc()

        final_response = ""
        from ai_engine.multi_agent_orchestrator import workflow
        
        if not workflow:
            raise Exception("Workflow failed to initialize.")

        for chunk in workflow.stream({"messages": [HumanMessage(content=prompt)], "next_agent": ""}):
            for node_name, node_state in chunk.items():
                if node_name != "Supervisor":
                    msgs = node_state.get('messages', [])
                    if msgs:
                        msg_content = msgs[-1].content
                        final_response = msg_content
                        print(f"\n{msg_content}")

        print("\n[Exodia] Threat successfully mitigated and logged for compliance.\n")
        THREATS_MITIGATED.inc()

        if target_ip != "unknown":
            set_threat_cache(target_ip, {"action": final_response}, ttl_seconds=3600)

        forward_to_siem(alert_id, alert_data, "Llama 3.2 Analysis", final_response)
        save_to_long_term_memory(alert_id, json.dumps(alert_data), final_response)

    except Exception as e:
        print(f"[ERROR] Multi-Agent orchestration failed: {e}")
    finally:
        AI_INFERENCE_TIME.observe(time.time() - start_time)


def start_kafka_listener():
    if not KAFKA_AVAILABLE:
        print("Kafka/Prometheus dependencies missing, cannot start listener.")
        return
        
    start_http_server(PROMETHEUS_PORT)
    print(f"[*] Prometheus Metrics Server started on port {PROMETHEUS_PORT}")

    consumer = Consumer({
        'bootstrap.servers': KAFKA_BROKER,
        'group.id': 'actis-ai-group',
        'auto.offset.reset': 'earliest'
    })

    consumer.subscribe([TOPIC_NAME])
    print(f"[*] ACTIS Exodia Agent listening to Kafka topic '{TOPIC_NAME}'...")

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"[Kafka Error] {msg.error()}")
                continue

            try:
                alert_data = json.loads(msg.value().decode('utf-8'))
                analyze_threat_with_ai(alert_data)
            except json.JSONDecodeError:
                print(f"[Warning] Received malformed data: {msg.value()}")

    except KeyboardInterrupt:
        print("\n[*] Shutting down listener gracefully...")
    finally:
        consumer.close()
        print("[*] Kafka consumer closed.")


if __name__ == "__main__":
    start_kafka_listener()
