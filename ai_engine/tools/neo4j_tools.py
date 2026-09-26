import os
from langchain_core.tools import tool

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "exodia_graph_secret")

try:
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    NEO4J_AVAILABLE = True
except ImportError:
    print("[Warning] neo4j python driver is missing. Threat graph queries will fail.")
    driver = None
    NEO4J_AVAILABLE = False
except Exception as e:
    print(f"[Warning] Failed to connect to Neo4j: {e}")
    driver = None
    NEO4J_AVAILABLE = False

@tool
def query_threat_graph(ip_address: str) -> str:
    """
    [PRODUCTION] Queries the Neo4j Threat Intelligence Knowledge Graph.
    Use this to find complex relationships (e.g., if an IP belongs to a known malicious ASN, 
    or is linked to a specific APT group or historical CVE).
    """
    print(f"\n[NEO4J GRAPH] Traversing Knowledge Graph for entity: {ip_address}...")
    
    if not NEO4J_AVAILABLE or not driver:
        return "ERROR: Neo4j database is offline or driver is missing."
        
    query = """
    MATCH (ip:IP {address: $ip})-[:BELONGS_TO]->(asn:ASN)
    OPTIONAL MATCH (asn)<-[:OPERATES_FROM]-(apt:ThreatActor)
    RETURN ip.address AS IP, asn.id AS ASN, apt.name AS ThreatActor
    """
    
    try:
        with driver.session() as session:
            result = session.run(query, ip=ip_address)
            records = list(result)
            
            if not records:
                return f"No known relationships found in the Knowledge Graph for {ip_address}."
                
            out = "GRAPH RELATIONSHIPS FOUND:\n"
            for r in records:
                out += f"- IP ({r['IP']}) -[BELONGS_TO]-> ASN ({r['ASN']})\n"
                if r['ThreatActor']:
                    out += f"- ASN ({r['ASN']}) <-[OPERATES_FROM]- ThreatActor ({r['ThreatActor']})\n"
            return out
    except Exception as e:
        return f"ERROR querying Neo4j: {str(e)}"
