import os
import redis
import json

# Connect to the local Redis container
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    # Test connection
    redis_client.ping()
except Exception as e:
    print(f"[Warning] Redis Cache is unreachable at {REDIS_HOST}:{REDIS_PORT} - {e}")
    redis_client = None

def check_threat_cache(ip_address: str) -> dict:
    """
    Checks if an IP address was recently analyzed.
    Prevents redundant, expensive LLM inferences on the same attacker IP.
    """
    if not redis_client:
        return None
        
    cached_result = redis_client.get(f"threat_ip:{ip_address}")
    if cached_result:
        print(f"\n[REDIS HOT CACHE HIT] IP {ip_address} found in memory. Bypassing LLM inference.")
        return json.loads(cached_result)
    
    return None

def set_threat_cache(ip_address: str, analysis_result: dict, ttl_seconds: int = 3600):
    """
    Caches the AI's verdict for a specific IP address.
    Defaults to keeping it in memory for 1 hour (3600 seconds).
    """
    if not redis_client:
        return
        
    print(f"[REDIS HOT CACHE SET] Caching verdict for IP {ip_address} for {ttl_seconds}s.")
    redis_client.setex(
        f"threat_ip:{ip_address}",
        ttl_seconds,
        json.dumps(analysis_result)
    )
