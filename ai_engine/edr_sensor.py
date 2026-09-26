import psutil
import time
import socket
import sys

def get_process_name(pid):
    try:
        return psutil.Process(pid).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return "Unknown"

def monitor_network():
    print("[+] Exodia EDR Sensor Initialized.")
    print("[+] Monitoring local Windows network connections...\n")
    
    seen_connections = set()
    
    # Ports we don't want to alert on (Standard Web/Local)
    ignored_ports = {80, 443, 8080, 9090, 9092, 3000, 2181, 7474, 7687}
    
    while True:
        try:
            # Get all internet connections (IPv4/IPv6, TCP/UDP)
            conns = psutil.net_connections(kind='inet')
            
            for conn in conns:
                # We care about connections talking to the outside world
                if conn.status == 'ESTABLISHED' and conn.raddr:
                    laddr = conn.laddr.ip
                    raddr_ip = conn.raddr.ip
                    raddr_port = conn.raddr.port
                    
                    # Ignore loopback/localhost traffic
                    if raddr_ip in ['127.0.0.1', '::1', '0.0.0.0']:
                        continue
                        
                    # Ignore safe ports to avoid spam
                    if raddr_port in ignored_ports:
                        continue
                        
                    connection_id = f"{raddr_ip}:{raddr_port}-{conn.pid}"
                    
                    if connection_id not in seen_connections:
                        seen_connections.add(connection_id)
                        process_name = get_process_name(conn.pid)
                        
                        alert = f"[EDR SENSOR] Suspicious Outbound Connection Detected!"
                        details = f"| Process: {process_name} (PID {conn.pid}) | Target: {raddr_ip}:{raddr_port}"
                        
                        # Print to stdout so the Exodia Desktop App can read it
                        print(f"{alert} {details}", flush=True)
                        
        except Exception as e:
            # psutil might throw access denied on some system processes, ignore
            pass
            
        time.sleep(2)

if __name__ == "__main__":
    monitor_network()
