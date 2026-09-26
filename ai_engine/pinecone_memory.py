import os
import json
from datetime import datetime, timezone

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "exodia-global-threat-memory")

pinecone_store = None

if PINECONE_API_KEY:
    try:
        from pinecone import Pinecone
        from langchain_pinecone import PineconeVectorStore
        from langchain_ollama import OllamaEmbeddings
        pc = Pinecone(api_key=PINECONE_API_KEY)
        embeddings = OllamaEmbeddings(model="llama3.2")
        pinecone_store = PineconeVectorStore(index_name=PINECONE_INDEX_NAME, embedding=embeddings)
    except Exception as e:
        print(f"[Warning] Pinecone cloud memory offline. Defaulting to local file. ({e})")
        pinecone_store = None

def save_to_long_term_memory(incident_id: str, threat_data: str, resolution: str):
    print(f"\n[PINECONE MEMORY] Uploading Incident {incident_id} to Cloud Long-Term Memory...")
    
    memory_document = f"Incident ID: {incident_id}\nThreat Context: {threat_data}\nSuccessful Resolution: {resolution}"
    
    if pinecone_store:
        try:
            pinecone_store.add_texts([memory_document], metadatas=[{"incident_id": incident_id, "type": "resolved_threat"}])
            print(f"[PINECONE MEMORY] Successfully crystallized incident {incident_id} into global memory.")
            return
        except Exception as e:
            print(f"[Warning] Failed to write to Pinecone: {e}")
            
    # Fallback to local JSONL
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    memory_file = os.path.join(log_dir, "incident_memory.jsonl")
    
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "incident_id": incident_id,
        "threat_data": threat_data,
        "resolution": resolution
    }
    
    try:
        with open(memory_file, "a") as f:
            f.write(json.dumps(payload) + "\n")
        print(f"[PINECONE MEMORY] Successfully crystallized incident {incident_id} into local memory log.")
    except Exception as e:
        print(f"[Error] Failed to write to local memory log: {e}")
