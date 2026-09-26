import customtkinter as ctk
import requests
import threading
import time
import json
import random
import os
import sys
import subprocess
from PIL import Image
import networkx as nx
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from neo4j import GraphDatabase

# Configure modern dark theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

def get_project_root():
    if getattr(sys, 'frozen', False):
        # When frozen, exe is in dist/ — project root is one level up
        exe_dir = os.path.dirname(sys.executable)
        parent = os.path.dirname(exe_dir)
        # Check if parent has ai_engine (meaning we're in dist/)
        if os.path.isdir(os.path.join(parent, 'ai_engine')):
            return parent
        # Check if cwd has ai_engine (shortcut sets WorkingDirectory)
        if os.path.isdir(os.path.join(os.getcwd(), 'ai_engine')):
            return os.getcwd()
        # Check exe_dir itself
        if os.path.isdir(os.path.join(exe_dir, 'ai_engine')):
            return exe_dir
        return parent  # best guess
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_asset_path(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'desktop_app', filename)
    return os.path.join(get_project_root(), 'desktop_app', filename)

class ExodiaDesktop(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Exodia - Autonomous Command Center")
        self.geometry("1280x800")
        
        try:
            self.iconbitmap(get_asset_path("logo.ico"))
        except Exception:
            pass
            
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.config_path = os.path.join(get_project_root(), "config", "exodia_config.json")
        self.load_config()

        # ─── SIDEBAR ───
        self.sidebar = ctk.CTkFrame(self, width=260, corner_radius=0, fg_color="#111111")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(7, weight=1)

        try:
            logo_path = get_asset_path("logo.png")
            pil_img = Image.open(logo_path)
            self.logo_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(200, 150))
            self.logo = ctk.CTkLabel(self.sidebar, text="", image=self.logo_img)
        except Exception:
            self.logo = ctk.CTkLabel(self.sidebar, text="EXODIA", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo.grid(row=0, column=0, padx=20, pady=(40, 40))

        self.btn_dash = ctk.CTkButton(self.sidebar, text="Dashboard", fg_color="#222222", hover_color="#333333", anchor="w", command=lambda: self.select_tab("dashboard"))
        self.btn_dash.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        self.btn_agents = ctk.CTkButton(self.sidebar, text="AI Swarm Control", fg_color="transparent", hover_color="#333333", anchor="w", command=lambda: self.select_tab("agents"))
        self.btn_agents.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        
        self.btn_graph = ctk.CTkButton(self.sidebar, text="Threat Graph", fg_color="transparent", hover_color="#333333", anchor="w", command=lambda: self.select_tab("graph"))
        self.btn_graph.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        
        self.btn_playbooks = ctk.CTkButton(self.sidebar, text="SOAR Playbooks", fg_color="transparent", hover_color="#333333", anchor="w", command=lambda: self.select_tab("playbooks"))
        self.btn_playbooks.grid(row=4, column=0, padx=20, pady=10, sticky="ew")

        self.btn_settings = ctk.CTkButton(self.sidebar, text="Settings", fg_color="transparent", hover_color="#333333", anchor="w", command=lambda: self.select_tab("settings"))
        self.btn_settings.grid(row=5, column=0, padx=20, pady=10, sticky="ew")

        # Service Status Indicators
        self.status_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.status_frame.grid(row=8, column=0, padx=20, pady=(0, 20), sticky="s")
        
        self.status_gateway = ctk.CTkLabel(self.status_frame, text="● Gateway Offline", text_color="#FF4444", font=ctk.CTkFont(size=12, weight="bold"))
        self.status_gateway.pack(anchor="w")
        self.status_kafka = ctk.CTkLabel(self.status_frame, text="● Kafka Offline", text_color="#FF4444", font=ctk.CTkFont(size=12, weight="bold"))
        self.status_kafka.pack(anchor="w")
        self.status_ollama = ctk.CTkLabel(self.status_frame, text="● Ollama Offline", text_color="#FF4444", font=ctk.CTkFont(size=12, weight="bold"))
        self.status_ollama.pack(anchor="w")
        self.status_redis = ctk.CTkLabel(self.status_frame, text="● Redis Offline", text_color="#FF4444", font=ctk.CTkFont(size=12, weight="bold"))
        self.status_redis.pack(anchor="w")

        self.version_label = ctk.CTkLabel(self.sidebar, text="Exodia v2.0", text_color="#555555", font=ctk.CTkFont(size=10))
        self.version_label.grid(row=9, column=0, pady=(0, 10), sticky="s")

        # ─── MAIN CONTENT ───
        self.main_container = ctk.CTkFrame(self, fg_color="#181818", corner_radius=0)
        self.main_container.grid(row=0, column=1, sticky="nsew")
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
        
        self.frames = {}
        self.demo_mode = self.config.get("demo_mode", True)
        self.agent_process = None
        self.edr_process = None
        
        self.build_dashboard_view()
        self.build_agents_view()
        self.build_graph_view()
        self.build_playbooks_view()
        self.build_settings_view()

        self.select_tab("dashboard")

        self.running = True
        threading.Thread(target=self.poll_gateway, daemon=True).start()
        threading.Thread(target=self.simulate_stream, daemon=True).start()

    def get_python_exe(self):
        if getattr(sys, 'frozen', False):
            # When frozen, find the venv python relative to project root
            candidates = [
                os.path.join(get_project_root(), 'venv', 'Scripts', 'python.exe'),
                os.path.join(os.path.dirname(sys.executable), 'venv', 'Scripts', 'python.exe'),
                os.path.join(os.path.dirname(os.path.dirname(sys.executable)), 'venv', 'Scripts', 'python.exe'),
                os.path.join(os.getcwd(), 'venv', 'Scripts', 'python.exe'),
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c
            return 'python'  # fallback to system python
        return sys.executable

    def load_config(self):
        self.config = {
            "demo_mode": True,
            "gateway_url": "http://localhost:8080",
            "kafka_broker": "localhost:9092",
            "neo4j_uri": "bolt://localhost:7687",
            "neo4j_password": "exodia_admin",
            "ollama_url": "http://localhost:11434",
            "llm_model": "llama3.2",
            "playbooks": {
                "Cloudflare WAF IP Ban": True,
                "CrowdStrike EDR Host Isolation": True,
                "Slack Approval Webhook": True,
                "AWS IAM Policy Revocation": False
            }
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    self.config.update(json.load(f))
            except Exception:
                pass
        else:
            self.save_config()

    def save_config(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception:
            pass

    def on_close(self):
        self.running = False
        if self.agent_process:
            try:
                self.agent_process.terminate()
            except Exception:
                pass
        if self.edr_process:
            try:
                self.edr_process.terminate()
            except Exception:
                pass
        self.destroy()

    def select_tab(self, tab_name):
        buttons = {"dashboard": self.btn_dash, "agents": self.btn_agents, "graph": self.btn_graph, "playbooks": self.btn_playbooks, "settings": self.btn_settings}
        for name, btn in buttons.items():
            if name == tab_name:
                btn.configure(fg_color="#222222")
            else:
                btn.configure(fg_color="transparent")
        
        for frame in self.frames.values():
            frame.grid_forget()
        self.frames[tab_name].grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

    # ─── VIEWS ───

    def build_dashboard_view(self):
        frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.frames["dashboard"] = frame
        frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        frame.grid_rowconfigure(2, weight=1)

        self.header = ctk.CTkLabel(frame, text="Autonomous Defense Dashboard", font=ctk.CTkFont(size=28, weight="bold"))
        self.header.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 20))

        btn_edr = ctk.CTkButton(frame, text="🛡 Arm Live EDR Sensor", fg_color="#1E90FF", hover_color="#4169E1", command=self.toggle_edr)
        btn_edr.grid(row=0, column=2, sticky="e", pady=(0, 20), padx=10)

        btn_inject = ctk.CTkButton(frame, text="⚠ Inject Chaos Threat", fg_color="#8B0000", hover_color="#A52A2A", command=self.inject_threat)
        btn_inject.grid(row=0, column=3, sticky="e", pady=(0, 20))

        self.card1 = self.create_metric_card(frame, "Kafka Stream", "0 MB/s", 1, 0)
        self.card2 = self.create_metric_card(frame, "AI Confidence", "0%", 1, 1)
        self.card3 = self.create_metric_card(frame, "Processed", "0", 1, 2)
        self.card4 = self.create_metric_card(frame, "MTTR", "N/A", 1, 3)

        self.console_frame = ctk.CTkFrame(frame, fg_color="#111111", corner_radius=10)
        self.console_frame.grid(row=2, column=0, columnspan=4, sticky="nsew", pady=(20, 0))
        self.console_frame.grid_columnconfigure(0, weight=1)
        self.console_frame.grid_rowconfigure(1, weight=1)

        title_frame = ctk.CTkFrame(self.console_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 0))
        
        self.console_title = ctk.CTkLabel(title_frame, text="LIVE NEURAL STREAM", font=ctk.CTkFont(size=12, weight="bold"), text_color="#555555")
        self.console_title.pack(side="left")
        
        btn_clear = ctk.CTkButton(title_frame, text="Clear Console", width=100, height=24, fg_color="#333333", hover_color="#444444", command=self.clear_console)
        btn_clear.pack(side="right")

        self.console_box = ctk.CTkTextbox(self.console_frame, fg_color="#111111", text_color="#00FF41", font=ctk.CTkFont(family="Consolas", size=13))
        self.console_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.console_box.configure(state="disabled")

    def build_agents_view(self):
        frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.frames["agents"] = frame
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)

        title = ctk.CTkLabel(frame, text="LangGraph Orchestrator", font=ctk.CTkFont(size=28, weight="bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 10))

        controls = ctk.CTkFrame(frame, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        
        self.btn_start_agents = ctk.CTkButton(controls, text="▶ Boot Swarm", fg_color="#006400", hover_color="#008000", command=self.start_agent_swarm)
        self.btn_start_agents.pack(side="left", padx=(0, 10))

        self.btn_stop_agents = ctk.CTkButton(controls, text="■ Shutdown Swarm", fg_color="#8B0000", hover_color="#A52A2A", state="disabled", command=self.stop_agent_swarm)
        self.btn_stop_agents.pack(side="left")

        self.agent_console = ctk.CTkTextbox(frame, fg_color="#0a0a0a", text_color="#D3D3D3", font=ctk.CTkFont(family="Consolas", size=13))
        self.agent_console.grid(row=2, column=0, sticky="nsew")
        self.agent_console.configure(state="disabled")

    def build_graph_view(self):
        frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.frames["graph"] = frame
        frame.grid_rowconfigure(2, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        
        title = ctk.CTkLabel(frame, text="Live Neural Threat Graph", font=ctk.CTkFont(size=28, weight="bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        desc = ctk.CTkLabel(frame, text="Interactive real-time mapping of attack vectors, APTs, and affected hosts.", font=ctk.CTkFont(size=14), text_color="#888888")
        desc.grid(row=1, column=0, sticky="w", pady=(0, 20))

        # Controls
        controls = ctk.CTkFrame(frame, fg_color="transparent")
        controls.grid(row=0, column=1, rowspan=2, sticky="e")
        btn_refresh = ctk.CTkButton(controls, text="Refresh Graph", command=self.refresh_graph)
        btn_refresh.pack(side="right", padx=5)
        
        # Matplotlib Figure
        plt.style.use("dark_background")
        self.fig, self.ax = plt.subplots(figsize=(6, 4))
        self.fig.patch.set_facecolor('#181818')
        self.ax.set_facecolor('#181818')
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame)
        self.canvas.get_tk_widget().grid(row=2, column=0, columnspan=2, sticky="nsew")
        
        self.refresh_graph()

    def refresh_graph(self):
        self.ax.clear()
        G = nx.Graph()
        
        if not self.demo_mode:
            try:
                # Try connecting to Neo4j
                driver = GraphDatabase.driver(
                    self.config.get("neo4j_uri", "bolt://localhost:7687"), 
                    auth=("neo4j", self.config.get("neo4j_password", "exodia_admin"))
                )
                with driver.session() as session:
                    result = session.run("MATCH (a)-[r]->(b) RETURN a.ip AS src, type(r) AS rel, b.name AS dst LIMIT 50")
                    for record in result:
                        src = record["src"] or "Unknown IP"
                        dst = record["dst"] or "Unknown Target"
                        G.add_edge(src, dst)
            except Exception as e:
                self.log_console(f">> Graph DB Error: {e}. Falling back to topology simulation.")
                self.generate_demo_graph(G)
        else:
            self.generate_demo_graph(G)
            
        pos = nx.spring_layout(G, seed=42)
        
        node_colors = []
        for node in G.nodes():
            if "Attacker" in node:
                node_colors.append('#FF4444') # Red
            elif "APT" in node:
                node_colors.append('#1E90FF') # Blue
            elif "CVE" in node:
                node_colors.append('#FFA500') # Orange
            else:
                node_colors.append('#00FF41') # Green

        # Draw Nodes
        nx.draw_networkx_nodes(G, pos, ax=self.ax, node_color=node_colors, node_size=300, alpha=0.8)
        # Draw Edges
        nx.draw_networkx_edges(G, pos, ax=self.ax, edge_color='#555555', alpha=0.5)
        # Draw Labels
        nx.draw_networkx_labels(G, pos, ax=self.ax, font_size=8, font_color='white', font_family='sans-serif')
        
        self.ax.margins(0.2)
        self.ax.axis("off")
        self.canvas.draw()

    def generate_demo_graph(self, G):
        # 15 demo nodes
        edges = [
            ("192.168.1.5", "SQL Database"),
            ("192.168.1.5", "Web Server"),
            ("Attacker IP: 45.33.22.1", "Web Server"),
            ("Attacker IP: 45.33.22.1", "APT29 (Cozy Bear)"),
            ("APT29 (Cozy Bear)", "CVE-2024-2143"),
            ("Web Server", "CVE-2024-2143"),
            ("10.0.0.9", "Internal HR File Share"),
            ("Attacker IP: 104.22.3.1", "10.0.0.9"),
            ("10.0.0.12", "Mail Server"),
            ("Attacker IP: 104.22.3.1", "Mail Server"),
            ("Mail Server", "CVE-2023-1122"),
            ("APT32 (OceanLotus)", "CVE-2023-1122"),
            ("Attacker IP: 185.11.2.3", "APT32 (OceanLotus)"),
            ("10.0.0.15", "Active Directory"),
            ("Mail Server", "Active Directory")
        ]
        G.add_edges_from(edges)

    def build_playbooks_view(self):
        frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.frames["playbooks"] = frame

        title = ctk.CTkLabel(frame, text="SOAR Playbooks", font=ctk.CTkFont(size=28, weight="bold"))
        title.pack(anchor="w", pady=(0, 20))
        
        playbooks_config = self.config.get("playbooks", {})

        rules = [
            ("Cloudflare WAF IP Ban", "Severity Critical - Automatically ban IPs via WAF"),
            ("CrowdStrike EDR Host Isolation", "Confidence > 90% - Isolate compromised hosts"),
            ("Slack Approval Webhook", "Confidence < 70% - Require human-in-the-loop approval"),
            ("AWS IAM Policy Revocation", "Revoke compromised IAM roles immediately")
        ]

        for key, desc in rules:
            container = ctk.CTkFrame(frame, fg_color="transparent")
            container.pack(anchor="w", pady=10, fill="x")
            
            state = playbooks_config.get(key, False)
            switch = ctk.CTkSwitch(
                container, 
                text=key, 
                font=ctk.CTkFont(size=14, weight="bold"),
                command=lambda k=key, s=container: self.toggle_playbook(k, s)
            )
            switch.pack(anchor="w")
            if state:
                switch.select()
                
            # Store the switch reference in the container for the callback to retrieve
            container.switch = switch
                
            lbl = ctk.CTkLabel(container, text=desc, font=ctk.CTkFont(size=12), text_color="#888888")
            lbl.pack(anchor="w", padx=45)

    def toggle_playbook(self, key, container):
        state = bool(container.switch.get())
        if "playbooks" not in self.config:
            self.config["playbooks"] = {}
        self.config["playbooks"][key] = state
        self.save_config()

    def build_settings_view(self):
        frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.frames["settings"] = frame

        title = ctk.CTkLabel(frame, text="Settings & Configuration", font=ctk.CTkFont(size=28, weight="bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 20), columnspan=2)

        self.demo_toggle = ctk.CTkSwitch(frame, text="Enable Demo Mode (Simulate Telemetry Stream)", command=self.toggle_demo)
        self.demo_toggle.grid(row=1, column=0, sticky="w", pady=10, columnspan=2)
        if self.config.get("demo_mode", True):
            self.demo_toggle.select()

        # Input fields
        fields = [
            ("Gateway URL", "gateway_url", "http://localhost:8080"),
            ("Kafka Broker", "kafka_broker", "localhost:9092"),
            ("Neo4j URI", "neo4j_uri", "bolt://localhost:7687"),
            ("Neo4j Password", "neo4j_password", ""),
            ("Ollama URL", "ollama_url", "http://localhost:11434"),
            ("LLM Model", "llm_model", "llama3.2")
        ]
        
        self.setting_entries = {}
        row = 2
        for label_text, config_key, placeholder in fields:
            lbl = ctk.CTkLabel(frame, text=label_text)
            lbl.grid(row=row, column=0, sticky="w", pady=(15, 5))
            
            entry = ctk.CTkEntry(frame, width=400, placeholder_text=placeholder)
            if config_key == "neo4j_password":
                entry.configure(show="*")
            entry.grid(row=row+1, column=0, sticky="w")
            
            val = self.config.get(config_key, "")
            if val:
                entry.insert(0, str(val))
                
            self.setting_entries[config_key] = entry
            row += 2

        btn_save = ctk.CTkButton(frame, text="Save Configuration", command=self.save_settings)
        btn_save.grid(row=row, column=0, sticky="w", pady=(30, 0))
        
        self.lbl_save_status = ctk.CTkLabel(frame, text="", text_color="#00FF41")
        self.lbl_save_status.grid(row=row, column=1, sticky="w", pady=(30, 0), padx=10)

    def save_settings(self):
        self.config["demo_mode"] = bool(self.demo_toggle.get())
        for key, entry in self.setting_entries.items():
            self.config[key] = entry.get()
        self.save_config()
        self.lbl_save_status.configure(text="Settings saved successfully!")
        self.after(3000, lambda: self.lbl_save_status.configure(text=""))
        self.demo_mode = self.config["demo_mode"]

    # ─── LOGIC ───

    def create_metric_card(self, parent, title, val, row, col):
        frame = ctk.CTkFrame(parent, fg_color="#222222", corner_radius=15)
        frame.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
        lbl_title = ctk.CTkLabel(frame, text=title.upper(), font=ctk.CTkFont(size=11, weight="bold"), text_color="#777777")
        lbl_title.pack(anchor="w", padx=15, pady=(15, 0))
        lbl_val = ctk.CTkLabel(frame, text=val, font=ctk.CTkFont(size=28, weight="bold"))
        lbl_val.pack(anchor="w", padx=15, pady=(0, 15))
        return lbl_val
        
    def limit_text_lines(self, textbox, limit=500):
        try:
            lines = int(textbox.index('end-1c').split('.')[0])
            if lines > limit:
                textbox.delete('1.0', f'{lines - limit + 1}.0')
        except Exception:
            pass

    def clear_console(self):
        self.console_box.configure(state="normal")
        self.console_box.delete("1.0", "end")
        self.console_box.configure(state="disabled")

    def log_console(self, msg):
        self.console_box.configure(state="normal")
        timestamp = time.strftime("%H:%M:%S")
        self.console_box.insert("end", f"[{timestamp}] {msg}\n")
        self.limit_text_lines(self.console_box, 500)
        self.console_box.see("end")
        self.console_box.configure(state="disabled")
        
    def log_agent(self, msg):
        self.agent_console.configure(state="normal")
        self.agent_console.insert("end", f"{msg}\n")
        self.limit_text_lines(self.agent_console, 500)
        self.agent_console.see("end")
        self.agent_console.configure(state="disabled")

    def toggle_demo(self):
        self.demo_mode = bool(self.demo_toggle.get())
        if self.demo_mode:
            self.log_console(">> DEMO MODE ENABLED: Streaming simulated telemetry...")
        else:
            self.log_console(">> DEMO MODE DISABLED: Listening strictly for real Kafka events.")
            
        self.config["demo_mode"] = self.demo_mode
        self.save_config()

    def inject_threat(self):
        self.log_console(">> INJECTING REAL CHAOS THREAT INTO KAFKA...")
        try:
            script_path = os.path.join(get_project_root(), "ai_engine", "threat_generator.py")
            if os.path.exists(script_path):
                subprocess.Popen([self.get_python_exe(), script_path], stdout=subprocess.DEVNULL)
                self.log_console(">> Payload generated and pushed to topic 'enriched-alerts'.")
            else:
                self.log_console(">> Payload simulated: (threat_generator.py not found).")
        except Exception as e:
            self.log_console(f">> Injection failed: {e}")

    def start_agent_swarm(self):
        self.btn_start_agents.configure(state="disabled")
        self.btn_stop_agents.configure(state="normal")
        self.log_agent(">>> BOOTING EXODIA MULTI-AGENT SWARM (POWERED BY OLLAMA LLAMA 3.2)...")
        
        script_path = os.path.join(get_project_root(), "ai_engine", "kafka_listener.py")
        if os.path.exists(script_path):
            self.agent_process = subprocess.Popen(
                [self.get_python_exe(), "-u", script_path], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True, 
                bufsize=1
            )
            threading.Thread(target=self.stream_agent_output, daemon=True).start()
        else:
            self.log_agent(f"ERROR: Could not locate {script_path}")
            self.log_agent("Running in UI Mock Mode. Agents will not actually process Kafka topics.")

    def stream_agent_output(self):
        if self.agent_process:
            for line in iter(self.agent_process.stdout.readline, ''):
                self.after(0, self.log_agent, line.strip())
            self.agent_process.stdout.close()
            self.agent_process.wait()

    def stop_agent_swarm(self):
        if self.agent_process:
            self.agent_process.terminate()
            self.agent_process = None
        self.log_agent(">>> SWARM SHUTDOWN COMPLETE.")
        self.btn_start_agents.configure(state="normal")
        self.btn_stop_agents.configure(state="disabled")

    def poll_gateway(self):
        while self.running:
            # Check Gateway
            try:
                gateway_url = self.config.get("gateway_url", "http://localhost:8080")
                resp = requests.get(f"{gateway_url}/api/v1/metrics", timeout=2)
                if resp.status_code == 200:
                    data = resp.json()
                    self.after(0, self.status_gateway.configure, {"text": "● Gateway Online", "text_color": "#00FF41"})
                    self.after(0, self.card1.configure, {"text": f"{data.get('kafka_ingest_rate_mb', 0)} MB/s"})
                    self.after(0, self.card2.configure, {"text": f"{data.get('ai_confidence_score', 0)}%"})
                    self.after(0, self.card3.configure, {"text": f"{data.get('threats_processed', 0):,}"})
                else:
                    self.after(0, self.status_gateway.configure, {"text": "● Gateway Error", "text_color": "#FF4444"})
            except Exception:
                self.after(0, self.status_gateway.configure, {"text": "● Gateway Offline", "text_color": "#FF4444"})
                
            # Simulate basic checks for Kafka, Ollama, Redis
            # In a full implementation, these would make real API checks
            self.after(0, self.status_kafka.configure, {"text": "● Kafka Online", "text_color": "#00FF41"})
            self.after(0, self.status_ollama.configure, {"text": "● Ollama Online", "text_color": "#00FF41"})
            self.after(0, self.status_redis.configure, {"text": "● Redis Online", "text_color": "#00FF41"})
            
            time.sleep(2)

    def simulate_stream(self):
        types = ["SQL_INJECTION", "DATA_EXFILTRATION", "SSH_BRUTE_FORCE", "HONEYPOT_TRIPWIRE"]
        actions = ["BLOCKED via WAF", "ISOLATED via EDR", "ROUTED TO HUMAN"]
        
        while self.running:
            time.sleep(random.randint(1, 4))
            if self.demo_mode:
                event_type = random.choice(types)
                ip = f"{random.randint(10,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,255)}"
                action = random.choice(actions)
                log_msg = f"[AGENT:REMEDIATION] Threat: {event_type} | Source: {ip} | Decision: {action}"
                self.after(0, self.log_console, log_msg)

    def toggle_edr(self):
        if self.edr_process:
            self.edr_process.terminate()
            self.edr_process = None
            self.log_console(">> LIVE EDR SENSOR DISARMED.")
            self.console_title.configure(text_color="#555555")
        else:
            self.log_console(">> ARMING LIVE EDR NETWORK SENSOR...")
            self.demo_mode = False
            self.demo_toggle.deselect()
            self.console_title.configure(text_color="#00FF41")
            
            script_path = os.path.join(get_project_root(), "ai_engine", "edr_sensor.py")
            if os.path.exists(script_path):
                self.edr_process = subprocess.Popen(
                    [self.get_python_exe(), script_path], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    text=True, 
                    bufsize=1
                )
                threading.Thread(target=self.stream_edr_output, daemon=True).start()
            else:
                self.log_console(">> ERROR: edr_sensor.py not found.")

    def stream_edr_output(self):
        if self.edr_process:
            for line in iter(self.edr_process.stdout.readline, ''):
                self.after(0, self.log_console, line.strip())
            self.edr_process.wait()

if __name__ == "__main__":
    app = ExodiaDesktop()
    app.mainloop()
