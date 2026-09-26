import os
import sys
import threading
import time
import webview
import subprocess
import json

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api_gateway.main import app
import uvicorn

def start_server():
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="error")

def get_project_root():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def get_python_exe():
    if getattr(sys, 'frozen', False):
        return os.path.join(get_project_root(), "venv", "Scripts", "python.exe")
    return sys.executable

class Api:
    def __init__(self):
        self.sensor_process = None
        self.kafka_process = None
        
    def toggleSwarm(self):
        print("Toggling Swarm...")
        if not self.kafka_process:
            py_exe = get_python_exe()
            kafka_path = os.path.join(get_project_root(), "ai_engine", "kafka_listener.py")
            if os.path.exists(kafka_path):
                self.kafka_process = subprocess.Popen([py_exe, kafka_path])
                return "Swarm Activated"
        else:
            self.kafka_process.terminate()
            self.kafka_process = None
            return "Swarm Deactivated"
        return "Kafka listener not found"
        
    def armSensor(self):
        print("Arming Live EDR Sensor...")
        if not self.sensor_process:
            py_exe = get_python_exe()
            sensor_path = os.path.join(get_project_root(), "ai_engine", "edr_sensor.py")
            if os.path.exists(sensor_path):
                self.sensor_process = subprocess.Popen([py_exe, sensor_path])
                return "Sensor Armed"
        else:
            self.sensor_process.terminate()
            self.sensor_process = None
            return "Sensor Disarmed"
        return "Sensor script not found"

if __name__ == '__main__':
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    
    # Wait for server to bind to port
    time.sleep(1)
    
    api = Api()
    
    window = webview.create_window(
        'Exodia - Autonomous Defense', 
        'http://127.0.0.1:8080/',
        width=1280, 
        height=800,
        js_api=api,
        background_color='#08080a'
    )
    
    webview.start(private_mode=False)
    
    # Cleanup on exit
    if api.sensor_process:
        api.sensor_process.terminate()
    if api.kafka_process:
        api.kafka_process.terminate()
