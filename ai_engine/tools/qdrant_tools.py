import os
from langchain_core.tools import tool

# Gracefully handle missing qdrant-client
try:
    from qdrant_client import QdrantClient
    from langchain_qdrant import QdrantVectorStore
    from langchain_ollama import OllamaEmbeddings
    QDRANT_AVAILABLE = True
except ImportError as e:
    print(f"[Warning] Qdrant dependencies missing: {e}")
    QDRANT_AVAILABLE = False

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)

vector_store = None

if QDRANT_AVAILABLE:
    try:
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        embeddings = OllamaEmbeddings(model="llama3.2")
        vector_store = QdrantVectorStore(client=client, collection_name="threat_intel", embedding=embeddings)
    except Exception as e:
        print(f"[Warning] Could not connect to Qdrant Database at {QDRANT_URL}: {e}")
        vector_store = None

@tool
def search_past_breaches(query: str) -> str:
    """
    [PRODUCTION] Performs a real semantic similarity search against the Qdrant Vector Database 
    to find historical CVEs and threat intelligence reports matching the current attack pattern.
    """
    print(f"\n[Qdrant Search] Performing cosine similarity search for: '{query}'")
    
    if not QDRANT_AVAILABLE or not vector_store:
        return "ERROR: Qdrant database is offline, unreachable, or dependencies are missing."
        
    try:
        docs = vector_store.similarity_search(query, k=3)
        if not docs:
            return "No historical matches found in the vector database."
            
        compiled_intel = "Found the following historical context:\n"
        for i, doc in enumerate(docs):
            compiled_intel += f"{i+1}. {doc.page_content}\n"
            
        return compiled_intel
    except Exception as e:
        return f"ERROR searching Qdrant: {str(e)}"
