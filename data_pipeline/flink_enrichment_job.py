from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import FlinkKafkaConsumer, FlinkKafkaProducer
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
import json

def filter_high_severity(event_str):
    """Parses JSON and filters out low-severity noise."""
    try:
        event = json.loads(event_str)
        # Only forward Medium, High, and Critical threats to the AI Brain
        if event.get('severity') in ['Medium', 'High', 'Critical']:
            return True
        return False
    except Exception:
        return False

def format_enriched_event(event_str):
    """Enriches the data before sending to the AI (e.g., adding a timestamp)."""
    event = json.loads(event_str)
    event['enriched_by'] = 'Apache Flink'
    return json.dumps(event)

def run_enrichment_job():
    print("[Exodia Flink] Starting real-time stream enrichment job...")
    
    # 1. Setup execution environment
    env = StreamExecutionEnvironment.get_execution_environment()
    
    # 2. Configure Kafka Consumer (Reading from Hubble eBPF sensor)
    kafka_consumer = FlinkKafkaConsumer(
        topics='network-alerts',
        deserialization_schema=SimpleStringSchema(),
        properties={'bootstrap.servers': 'localhost:9092', 'group.id': 'flink-enrichment-group'}
    )
    
    stream = env.add_source(kafka_consumer)
    
    # 3. Apply Transformations (Filter Noise -> Enrich)
    enriched_stream = stream \
        .filter(filter_high_severity) \
        .map(format_enriched_event, output_type=Types.STRING())
        
    # 4. Configure Kafka Producer (Writing to the AI Agent's queue)
    kafka_producer = FlinkKafkaProducer(
        topic='enriched-alerts',
        serialization_schema=SimpleStringSchema(),
        producer_config={'bootstrap.servers': 'localhost:9092'}
    )
    
    enriched_stream.add_sink(kafka_producer)
    
    # 5. Execute the Flink Graph
    env.execute("Exodia_Threat_Enrichment_Job")

if __name__ == '__main__':
    run_enrichment_job()
