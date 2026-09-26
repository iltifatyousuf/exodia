from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import requests
import json

default_args = {
    'owner': 'exodia_admin',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def fetch_cve_data():
    """Simulates fetching the latest CVEs from the National Vulnerability Database (NVD)."""
    print("[Exodia Data Pipeline] Fetching daily threat intel from NVD...")
    # In production, this hits the NVD API
    simulated_cves = [
        {"id": "CVE-2024-0001", "description": "Critical buffer overflow in Edge Router.", "severity": "HIGH"},
        {"id": "CVE-2024-0002", "description": "SQL injection in legacy billing system.", "severity": "CRITICAL"}
    ]
    
    with open('/tmp/daily_cves.json', 'w') as f:
        json.dump(simulated_cves, f)
    print(f"Fetched {len(simulated_cves)} critical vulnerabilities.")

def embed_into_qdrant():
    """Simulates embedding the CVE data into the local Qdrant Vector Database."""
    print("[Exodia Data Pipeline] Generating vector embeddings for Qdrant...")
    with open('/tmp/daily_cves.json', 'r') as f:
        cves = json.load(f)
        
    for cve in cves:
        print(f"-> Upserting {cve['id']} into Qdrant collection 'threat_intel'...")
    
    print("Qdrant successfully updated. Exodia AI agents now have the latest threat knowledge.")

with DAG('exodia_nightly_threat_intel',
         default_args=default_args,
         schedule_interval='@daily',
         catchup=False) as dag:

    fetch_task = PythonOperator(
        task_id='fetch_nvd_cves',
        python_callable=fetch_cve_data
    )

    embed_task = PythonOperator(
        task_id='embed_to_qdrant',
        python_callable=embed_into_qdrant
    )

    fetch_task >> embed_task
