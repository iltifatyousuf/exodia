import os
import json
import asyncio
import logging
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import redis
from confluent_kafka import Consumer, KafkaException
import requests
import prometheus_client

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Exodia API Gateway")

ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,https://actis-exodia.vercel.app").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "exodia_config.json")
METRICS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "metrics.json")
AUDIT_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "siem_audit.jsonl")

def load_config() -> Dict[str, Any]:
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {}

def save_config(config_data: Dict[str, Any]):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config_data, f, indent=2)

@app.get("/api/v1/health")
def health_check():
    config = load_config()
    
    # Check Redis
    redis_status = "offline"
    try:
        r = redis.Redis(
            host=config.get("redis_host", "localhost"), 
            port=config.get("redis_port", 6379), 
            socket_timeout=1
        )
        if r.ping():
            redis_status = "online"
    except Exception:
        pass

    # Check Kafka
    kafka_status = "offline"
    try:
        c = Consumer({
            'bootstrap.servers': config.get("kafka_broker", "localhost:9092"),
            'group.id': 'health_check_group',
            'socket.timeout.ms': 1000
        })
        topics = c.list_topics(timeout=1)
        if topics:
            kafka_status = "online"
    except Exception:
        pass
    
    # Check Ollama
    ollama_status = "offline"
    try:
        ollama_url = config.get("ollama_url", "http://localhost:11434")
        resp = requests.get(f"{ollama_url}/api/tags", timeout=1)
        if resp.status_code == 200:
            ollama_status = "online"
    except Exception:
        pass

    return {
        "status": "online", 
        "services": {
            "kafka": kafka_status,
            "redis": redis_status,
            "ollama": ollama_status
        }
    }

@app.get("/api/v1/metrics")
def get_metrics():
    """Returns real counters from the shared metrics file or defaults."""
    # Prometheus client imported as requested, though reading from JSON
    # registry = prometheus_client.CollectorRegistry()
    try:
        with open(METRICS_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not read metrics.json: {e}")
        return {
            "kafka_ingest_rate_mb": 0,
            "ai_confidence_score": 0.0,
            "threats_processed": 0,
            "active_nodes": 0,
            "qdrant_vectors": "0"
        }

@app.get("/api/v1/config")
def get_config():
    return load_config()

@app.post("/api/v1/config")
async def update_config(request: Request):
    try:
        new_config = await request.json()
        current_config = load_config()
        current_config.update(new_config)
        save_config(current_config)
        return {"status": "success", "message": "Config updated"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.websocket("/api/v1/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    config = load_config()
    
    # Try Kafka first
    consumer = None
    try:
        consumer = Consumer({
            'bootstrap.servers': config.get("kafka_broker", "localhost:9092"),
            'group.id': 'websocket_stream_group',
            'auto.offset.reset': 'latest'
        })
        topic = config.get("kafka_topic", "enriched-alerts")
        consumer.subscribe([topic])
        logger.info(f"Subscribed to Kafka topic {topic}")
    except Exception as e:
        logger.warning(f"Failed to connect to Kafka for streaming: {e}")
        consumer = None

    try:
        if consumer:
            while True:
                msg = consumer.poll(1.0)
                if msg is None:
                    await asyncio.sleep(0.1)
                    continue
                if msg.error():
                    logger.error(f"Consumer error: {msg.error()}")
                    continue
                
                payload = msg.value().decode('utf-8')
                await websocket.send_text(payload)
                await asyncio.sleep(0.1)
        else:
            # Fallback to tailing siem_audit.jsonl
            logger.info(f"Falling back to tailing {AUDIT_LOG_PATH}")
            if not os.path.exists(AUDIT_LOG_PATH):
                os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
                with open(AUDIT_LOG_PATH, "w") as f:
                    pass # Create if not exists
                    
            with open(AUDIT_LOG_PATH, "r") as f:
                f.seek(0, os.SEEK_END)
                while True:
                    line = f.readline()
                    if not line:
                        await asyncio.sleep(0.5)
                        continue
                    try:
                        # Ensure it's valid JSON before sending
                        json.loads(line) 
                        await websocket.send_text(line.strip())
                    except Exception:
                        pass
    except Exception as e:
        logger.info(f"WebSocket disconnected: {e}")
    finally:
        if consumer:
            consumer.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
