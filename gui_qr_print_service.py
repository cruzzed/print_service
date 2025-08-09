import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import sqlite3
import requests
import tempfile
import os
import platform
import subprocess
import uuid
import threading
import json
import queue
from datetime import datetime

class ThreadSafeDatabaseManager:
    """Thread-safe database manager using a worker thread and queue"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.operation_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        
        # Initialize database in worker thread
        self._execute_operation('init_db', None, None)
    
    def _worker(self):
        """Worker thread that handles all database operations"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA journal_mode=WAL')  # Enable WAL mode for better concurrency
        
        while True:
            try:
                operation = self.operation_queue.get(timeout=1)
                if operation is None:  # Shutdown signal
                    break
                
                op_type, query, params = operation
                
                try:
                    if op_type == 'init_db':
                        cursor = conn.cursor()
                        cursor.execute('''
                            CREATE TABLE IF NOT EXISTS print_history (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                url TEXT NOT NULL,
                                print_type TEXT,
                                qr_data TEXT,
                                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                                status TEXT DEFAULT 'completed'
                            )
                        ''')
                        conn.commit()
                        self.result_queue.put(('success', None))
                        
                    elif op_type == 'insert':
                        cursor = conn.cursor()
                        cursor.execute(query, params)
                        conn.commit()
                        self.result_queue.put(('success', cursor.lastrowid))
                        
                    elif op_type == 'update':
                        cursor = conn.cursor()
                        cursor.execute(query, params)
                        conn.commit()
                        self.result_queue.put(('success', cursor.rowcount))
                        
                    elif op_type == 'delete':
                        cursor = conn.cursor()
                        cursor.execute(query, params)
                        conn.commit()
                        self.result_queue.put(('success', cursor.rowcount))
                        
                    elif op_type == 'select':
                        cursor = conn.cursor()
                        cursor.execute(query, params)
                        results = cursor.fetchall()
                        self.result_queue.put(('success', results))
                        
                    elif op_type == 'select_one':
                        cursor = conn.cursor()
                        cursor.execute(query, params)
                        result = cursor.fetchone()
                        self.result_queue.put(('success', result))
                        
                except Exception as e:
                    self.result_queue.put(('error', str(e)))
                    
            except queue.Empty:
                continue
            except Exception as e:
                self.result_queue.put(('error', str(e)))
        
        conn.close()
    
    def _execute_operation(self, op_type, query, params, timeout=5):
        """Execute a database operation and return the result"""
        self.operation_queue.put((op_type, query, params))
        
        try:
            status, result = self.result_queue.get(timeout=timeout)
            if status == 'error':
                raise Exception(f"Database error: {result}")
            return result
        except queue.Empty:
            raise Exception("Database operation timed out")
    
    def insert(self, query, params):
        """Insert data and return the last row id"""
        return self._execute_operation('insert', query, params)
    
    def update(self, query, params):
        """Update data and return the number of affected rows"""
        return self._execute_operation('update', query, params)
    
    def delete(self, query, params):
        """Delete data and return the number of affected rows"""
        return self._execute_operation('delete', query, params)
    
    def select(self, query, params=None):
        """Select multiple rows"""
        return self._execute_operation('select', query, params or ())
    
    def select_one(self, query, params=None):
        """Select a single row"""
        return self._execute_operation('select_one', query, params or ())
    
    def close(self):
        """Close the database manager"""
        self.operation_queue.put(None)
        self.worker_thread.join(timeout=2)

class QRPDFPrinter:
    def __init__(self, root):
        self.root = root
        self.root.title("QR PDF Printer v1.01")
        self.root.state('zoomed')  # Windows fullscreen
        self.root.attributes('-zoomed', True)  # Linux fullscreen
        try:
            self.root.attributes('-fullscreen', True)  # Cross-platform fullscreen
        except:
            pass
        
        # Status timer for error display
        self.status_timer = None
        
        # Load configuration
        self.load_config()
        
        # Initialize database
        self.init_database()
        
        # Create GUI
        self.create_widgets()
        
        # Load history
        self.refresh_history()
        
        # Focus on QR input field
        self.qr_entry.focus_set()
        
    def get_media_options(self, printer_type_id):
        """Get available media options for a printer type"""
        if printer_type_id in self.config["printer_types"]:
            return self.config["printer_types"][printer_type_id].get("media_options", ["auto (printer default)"])
        return ["auto (printer default)"]
    
    def get_printer_types(self):
        """Get all configured printer types"""
        return list(self.config["printer_types"].keys())
    
    def get_valid_prefixes(self):
        """Get all valid QR prefixes"""
        prefixes = []
        for type_config in self.config["printer_types"].values():
            prefixes.append(type_config["prefix"])
        return prefixes
    
    def get_printer_type_by_prefix(self, prefix):
        """Get printer type ID by QR prefix"""
        for type_id, type_config in self.config["printer_types"].items():
            if type_config["prefix"] == prefix:
                return type_id
        return None
    
    def add_printer_type(self, type_id, display_name, prefix, media_options=None):
        """Add a new printer type"""
        if media_options is None:
            media_options = ["auto (printer default)"]
        
        self.config["printer_types"][type_id] = {
            "display_name": display_name,
            "prefix": prefix,
            "printer_name": "default",
            "media": "auto (printer default)",
            "options": [],
            "media_options": media_options
        }
        self.save_config()
    
    def remove_printer_type(self, type_id):
        """Remove a printer type"""
        if type_id in self.config["printer_types"] and len(self.config["printer_types"]) > 1:
            del self.config["printer_types"][type_id]
            self.save_config()
            return True
        return False
    
    def load_config(self):
        """Load printer configuration from JSON file"""
        self.config_file = "printer_config.json"
        
        # Default configuration
        self.config = {
            "printer_types": {
                "label": {
                    "display_name": "Label Printer",
                    "prefix": "label",
                    "printer_name": "default",
                    "media": "auto (printer default)",
                    "options": [],
                    "media_options": [
                        "auto (printer default)",
                        "Custom.2x1in",
                        "Custom.4x6in", 
                        "Custom.51x25mm",
                        "Custom.102x51mm",
                        "Custom.4x2in",
                        "Custom.3x1in",
                        "Custom.62x29mm",
                        "na_index-4x6_4x6in",
                        "om_small-photo_100x150mm"
                    ]
                },
                "receipt": {
                    "display_name": "Receipt Printer",
                    "prefix": "receipt",
                    "printer_name": "default",
                    "media": "auto (printer default)",
                    "options": [],
                    "media_options": [
                        "auto (printer default)",
                        "Receipt",
                        "Custom.3x11in",
                        "Custom.80mm",
                        "Custom.58mm",
                        "Custom.57x32000mm",
                        "Custom.80x200mm"
                    ]
                }
            },
            "settings": {
                "auto_print": True,
                "auto_clear": True,
                "timeout": 30,
                "qr_separator": ":",
                "allow_custom_types": True
            }
        }
        
        # Load config file if it exists
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    
                    # Handle backward compatibility with old "printers" format
                    if "printers" in loaded_config and "printer_types" not in loaded_config:
                        self._migrate_old_config(loaded_config)
                    else:
                        # Merge with defaults to ensure all keys exist
                        if "printer_types" in loaded_config:
                            self.config["printer_types"].update(loaded_config["printer_types"])
                        if "settings" in loaded_config:
                            self.config["settings"].update(loaded_config["settings"])
                            
                print(f"Configuration loaded from {self.config_file}")
            except Exception as e:
                print(f"Error loading config: {e}")
                # Don't show dialog for config warnings - just log them
        else:
            # Create default config file
            self.save_config()
            print(f"Created default configuration file: {self.config_file}")
    
    def _migrate_old_config(self, old_config):
        """Migrate old printer config format to new dynamic format"""
        if "printers" in old_config:
            for old_type, old_settings in old_config["printers"].items():
                if old_type in self.config["printer_types"]:
                    self.config["printer_types"][old_type]["printer_name"] = old_settings.get("name", "default")
                    self.config["printer_types"][old_type]["media"] = old_settings.get("media", "auto (printer default)")
                    self.config["printer_types"][old_type]["options"] = old_settings.get("options", [])
        
        if "settings" in old_config:
            self.config["settings"].update(old_config["settings"])
        
        # Save migrated config
        self.save_config()
        print("Migrated old configuration format to new dynamic format")
    
    def save_config(self):
        """Save current configuration to JSON file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Config save error: {e}")
            # Don't show dialog for config save errors - just log them
    
    def get_available_printers(self):
        """Get list of available printers on the system"""
        try:
            system = platform.system()
            printers = []
            
            if system == "Windows":
                # Use PowerShell to get printer names
                result = subprocess.run([
                    "powershell", "-Command", 
                    "Get-Printer | Select-Object Name | ForEach-Object { $_.Name }"
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    printers = [line.strip() for line in result.stdout.split('\n') if line.strip()]
                
            elif system == "Darwin":  # macOS
                # Use lpstat to get printer names
                result = subprocess.run(["lpstat", "-p"], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if line.startswith('printer '):
                            printer_name = line.split()[1]
                            printers.append(printer_name)
                            
            elif system == "Linux":
                # Use lpstat to get printer names
                result = subprocess.run(["lpstat", "-p"], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if line.startswith('printer '):
                            printer_name = line.split()[1]
                            printers.append(printer_name)
            
            return printers
            
        except Exception as e:
            print(f"Error getting printers: {e}")
            return []
    
    def init_database(self):
        """Initialize thread-safe database manager"""
        self.db_manager = ThreadSafeDatabaseManager('printer_history.db')
    
    def log(self, message):
        """Add message to log with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def create_widgets(self):
        """Create the main GUI widgets"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # QR Scanner Input section (main feature)
        scanner_frame = ttk.LabelFrame(main_frame, text="QR Code Scanner Input", padding="10")
        scanner_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        scanner_frame.columnconfigure(1, weight=1)
        
        # Instructions
        instruction_text = "Scan QR code with handheld scanner or type/paste QR data:"
        ttk.Label(scanner_frame, text=instruction_text, font=('TkDefaultFont', 9)).grid(
            row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # QR Input field
        ttk.Label(scanner_frame, text="QR Data:", font=('TkDefaultFont', 10, 'bold')).grid(
            row=1, column=0, sticky=tk.W, padx=(0, 10))
        
        self.qr_var = tk.StringVar()
        self.qr_entry = ttk.Entry(scanner_frame, textvariable=self.qr_var, 
                                 font=('TkDefaultFont', 11), width=50)
        self.qr_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        self.qr_entry.bind('<Return>', self.on_qr_enter)
        self.qr_entry.bind('<KeyRelease>', self.on_qr_input_change)
        
        self.process_btn = ttk.Button(scanner_frame, text="Process & Print", 
                                    command=self.process_qr_input, state='disabled')
        self.process_btn.grid(row=1, column=2)
        
        # Status display
        self.status_var = tk.StringVar(value="Ready - waiting for QR code...")
        self.status_label = ttk.Label(scanner_frame, textvariable=self.status_var, 
                                     font=('TkDefaultFont', 10), foreground='blue')
        self.status_label.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Quick action buttons
        action_frame = ttk.Frame(scanner_frame)
        action_frame.grid(row=3, column=0, columnspan=3, pady=(10, 0))
        
        ttk.Button(action_frame, text="Clear Input", 
                  command=self.clear_input).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_frame, text="Focus Input", 
                  command=lambda: self.qr_entry.focus_set()).pack(side=tk.LEFT, padx=(0, 5))
        
        # Auto-print setting from config
        self.auto_print_var = tk.BooleanVar(value=self.config['settings']['auto_print'])
        ttk.Checkbutton(action_frame, text="Auto-print on scan", 
                       variable=self.auto_print_var).pack(side=tk.LEFT, padx=(10, 0))
        
        # Printer configuration section
        config_frame = ttk.LabelFrame(main_frame, text="Printer Configuration", padding="5")
        config_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Create dynamic printer configuration
        self.create_dynamic_printer_config(config_frame)
        
        # Current job info
        job_frame = ttk.LabelFrame(main_frame, text="Current Job", padding="5")
        job_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        job_frame.columnconfigure(1, weight=1)
        
        self.job_type_var = tk.StringVar(value="None")
        self.job_url_var = tk.StringVar(value="None")
        
        ttk.Label(job_frame, text="Type:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Label(job_frame, textvariable=self.job_type_var, font=('TkDefaultFont', 9, 'bold')).grid(
            row=0, column=1, sticky=tk.W)
        
        ttk.Label(job_frame, text="URL:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Label(job_frame, textvariable=self.job_url_var, font=('TkDefaultFont', 8)).grid(
            row=1, column=1, sticky=(tk.W, tk.E))
        
        # History section
        history_frame = ttk.LabelFrame(main_frame, text="Print History", padding="5")
        history_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        history_frame.columnconfigure(0, weight=1)
        history_frame.rowconfigure(0, weight=1)
        
        # Treeview for history
        columns = ('Type', 'URL', 'Status', 'Time')
        self.history_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=10)
        
        # Configure columns
        self.history_tree.heading('Type', text='Type')
        self.history_tree.heading('URL', text='URL')
        self.history_tree.heading('Status', text='Status')
        self.history_tree.heading('Time', text='Time')
        
        self.history_tree.column('Type', width=80)
        self.history_tree.column('URL', width=350)
        self.history_tree.column('Status', width=100)
        self.history_tree.column('Time', width=120)
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        self.history_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # History buttons
        hist_btn_frame = ttk.Frame(history_frame)
        hist_btn_frame.grid(row=1, column=0, columnspan=2, pady=(5, 0))
        
        ttk.Button(hist_btn_frame, text="Reprint Selected", 
                  command=self.reprint_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(hist_btn_frame, text="Delete Selected", 
                  command=self.delete_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(hist_btn_frame, text="Clear All", 
                  command=self.clear_history).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(hist_btn_frame, text="Refresh", 
                  command=self.refresh_history).pack(side=tk.LEFT)
        
        # Log area at bottom
        log_frame = ttk.LabelFrame(main_frame, text="Activity Log", padding="5")
        log_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, width=80)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Bind events
        self.history_tree.bind('<Double-1>', self.on_history_double_click)
        
        # Bind window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Global key binding for quick access
        self.root.bind('<F1>', lambda e: self.qr_entry.focus_set())
        self.root.bind('<Escape>', lambda e: self.clear_input())
        
        # Initial log message (after log widget is created)
        self.log("QR PDF Printer ready. Scan QR code or type QR data in the input field above.")
    
    def create_dynamic_printer_config(self, parent_frame):
        """Create dynamic printer configuration UI"""
        # Store references to UI elements
        self.printer_vars = {}
        self.media_vars = {}
        self.printer_combos = {}
        self.media_combos = {}
        
        # Create notebook for better organization
        notebook = ttk.Notebook(parent_frame)
        notebook.pack(fill='both', expand=True)
        
        # QR Settings tab
        qr_tab = ttk.Frame(notebook)
        notebook.add(qr_tab, text="QR Settings")
        
        # Separator setting
        ttk.Label(qr_tab, text="QR Separator:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.separator_var = tk.StringVar(value=self.config["settings"].get("qr_separator", ":"))
        separator_entry = ttk.Entry(qr_tab, textvariable=self.separator_var, width=5)
        separator_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(qr_tab, text="Valid Prefixes:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.prefixes_label = ttk.Label(qr_tab, text=", ".join(self.get_valid_prefixes()), 
                                       font=('TkDefaultFont', 9, 'bold'))
        self.prefixes_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Printer Types tab
        printers_tab = ttk.Frame(notebook)
        notebook.add(printers_tab, text="Printer Types")
        
        # Create scrollable frame for printer types
        canvas = tk.Canvas(printers_tab)
        scrollbar = ttk.Scrollbar(printers_tab, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Create printer type configurations
        self.refresh_printer_type_config()
        
        # Add buttons frame
        btn_frame = ttk.Frame(parent_frame)
        btn_frame.pack(fill='x', pady=(5, 0))
        
        ttk.Button(btn_frame, text="Add Printer Type", 
                  command=self.add_new_printer_type).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Remove Selected", 
                  command=self.remove_selected_printer_type).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Refresh Printers", 
                  command=self.refresh_all_printer_lists).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Save Configuration", 
                  command=self.save_all_printer_config).pack(side=tk.LEFT)
    
    def refresh_printer_type_config(self):
        """Refresh the dynamic printer type configuration UI"""
        # Clear existing widgets
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        self.printer_vars.clear()
        self.media_vars.clear()
        self.printer_combos.clear()
        self.media_combos.clear()
        
        available_printers = ['default'] + self.get_available_printers()
        
        row = 0
        for type_id, type_config in self.config["printer_types"].items():
            # Type frame
            type_frame = ttk.LabelFrame(self.scrollable_frame, text=type_config["display_name"], padding="5")
            type_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
            type_frame.columnconfigure(1, weight=1)
            type_frame.columnconfigure(3, weight=1)
            
            # Prefix
            ttk.Label(type_frame, text="Prefix:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
            prefix_var = tk.StringVar(value=type_config["prefix"])
            prefix_entry = ttk.Entry(type_frame, textvariable=prefix_var, width=15)
            prefix_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 10))
            
            # Store reference for saving
            setattr(self, f"{type_id}_prefix_var", prefix_var)
            
            # Printer selection
            ttk.Label(type_frame, text="Printer:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
            printer_var = tk.StringVar(value=type_config["printer_name"])
            printer_combo = ttk.Combobox(type_frame, textvariable=printer_var, values=available_printers, width=25)
            printer_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
            
            # Media selection
            ttk.Label(type_frame, text="Media:").grid(row=1, column=2, sticky=tk.W, padx=(0, 10))
            media_var = tk.StringVar(value=type_config["media"])
            media_combo = ttk.Combobox(type_frame, textvariable=media_var, 
                                     values=type_config["media_options"], width=20)
            media_combo.grid(row=1, column=3, sticky=(tk.W, tk.E), padx=(0, 10))
            
            # Store references
            self.printer_vars[type_id] = printer_var
            self.media_vars[type_id] = media_var
            self.printer_combos[type_id] = printer_combo
            self.media_combos[type_id] = media_combo
            
            row += 1
        
        # Update prefixes display
        self.prefixes_label.configure(text=", ".join(self.get_valid_prefixes()))
    
    def add_new_printer_type(self):
        """Add a new printer type"""
        dialog = PrinterTypeDialog(self.root, self)
        self.root.wait_window(dialog.dialog)
        if dialog.result:
            type_id, display_name, prefix, media_options = dialog.result
            if type_id not in self.config["printer_types"]:
                self.add_printer_type(type_id, display_name, prefix, media_options)
                self.refresh_printer_type_config()
                self.log(f"Added new printer type: {display_name}")
            else:
                error_msg = f"Printer type '{type_id}' already exists!"
                self.log(error_msg)
                self.update_status(error_msg, 'red', auto_reset=True)
    
    def remove_selected_printer_type(self):
        """Remove a selected printer type"""
        types = list(self.config["printer_types"].keys())
        if len(types) <= 1:
            self.log("Cannot remove the last printer type!")
            self.update_status("Cannot remove the last printer type!", 'red', auto_reset=True)
            return
        
        dialog = PrinterTypeSelectionDialog(self.root, types)
        self.root.wait_window(dialog.dialog)
        if dialog.result:
            type_id = dialog.result
            if self.remove_printer_type(type_id):
                self.refresh_printer_type_config()
                self.log(f"Removed printer type: {type_id}")
            else:
                error_msg = "Cannot remove printer type!"
                self.log(error_msg)
                self.update_status(error_msg, 'red', auto_reset=True)
    
    def refresh_all_printer_lists(self):
        """Refresh all printer dropdown lists"""
        available_printers = ['default'] + self.get_available_printers()
        for combo in self.printer_combos.values():
            combo['values'] = available_printers
        self.log("Printer lists refreshed")
    
    def save_all_printer_config(self):
        """Save all printer configuration changes"""
        try:
            # Update separator
            self.config["settings"]["qr_separator"] = self.separator_var.get()
            
            # Update printer configurations
            for type_id in self.config["printer_types"]:
                if type_id in self.printer_vars:
                    self.config["printer_types"][type_id]["printer_name"] = self.printer_vars[type_id].get()
                    self.config["printer_types"][type_id]["media"] = self.media_vars[type_id].get()
                
                # Update prefix if it exists
                prefix_var = getattr(self, f"{type_id}_prefix_var", None)
                if prefix_var:
                    self.config["printer_types"][type_id]["prefix"] = prefix_var.get()
            
            # Update auto-print setting
            self.config["settings"]["auto_print"] = self.auto_print_var.get()
            
            self.save_config()
            self.log("All printer configuration saved")
            self.update_status("Configuration saved successfully!", 'green', auto_reset=True)
            
            # Refresh prefixes display
            self.prefixes_label.configure(text=", ".join(self.get_valid_prefixes()))
            
        except Exception as e:
            self.log(f"Error saving configuration: {e}")
            self.update_status(f"Failed to save configuration: {e}", 'red', auto_reset=True)
    
    # Note: Legacy methods removed - now using dynamic configuration
    
    def update_status(self, message, color='blue', auto_reset=False):
        """Update status label with optional auto-reset to Ready"""
        # Cancel any existing timer
        if self.status_timer:
            self.root.after_cancel(self.status_timer)
            self.status_timer = None
        
        self.status_var.set(message)
        self.status_label.configure(foreground=color)
        
        # Set timer to reset to Ready after 5 seconds for errors
        if auto_reset and color in ['red', 'orange']:
            self.status_timer = self.root.after(5000, self._reset_status_to_ready)
    
    def _reset_status_to_ready(self):
        """Reset status to Ready after error display"""
        self.status_var.set("Ready - waiting for QR code...")
        self.status_label.configure(foreground='blue')
        self.status_timer = None
    
    def on_qr_input_change(self, event):
        """Handle changes in QR input field"""
        qr_data = self.qr_var.get().strip()
        if qr_data:
            self.process_btn.configure(state='normal')
            # Try to parse and show preview
            try:
                separator = self.config["settings"].get("qr_separator", ":")
                if separator in qr_data and qr_data.count(separator) >= 1:
                    parts = qr_data.split(separator, 1)
                    if len(parts) == 2:
                        prefix, url = parts
                        printer_type_id = self.get_printer_type_by_prefix(prefix.lower())
                        
                        if printer_type_id:
                            type_config = self.config["printer_types"][printer_type_id]
                            self.job_type_var.set(type_config["display_name"])
                            display_url = url if len(url) <= 60 else url[:57] + "..."
                            self.job_url_var.set(display_url)
                            self.update_status(f"Ready to print {type_config['display_name']} - Press Enter or click Process", 'green')
                            return
                
                valid_prefixes = self.get_valid_prefixes()
                separator = self.config["settings"].get("qr_separator", ":")
                self.job_type_var.set("Invalid Format")
                self.job_url_var.set(f"Expected: prefix{separator}url")
                self.update_status(f"Invalid QR format. Expected prefixes: {', '.join(valid_prefixes)}", 'red')
                
            except:
                self.job_type_var.set("Parsing...")
                self.job_url_var.set("...")
        else:
            self.process_btn.configure(state='disabled')
            self.job_type_var.set("None")
            self.job_url_var.set("None")
            self.update_status("Ready - waiting for QR code...", 'blue')
    
    def on_qr_enter(self, event):
        """Handle Enter key in QR input field"""
        if self.auto_print_var.get():
            self.process_qr_input()
    
    def clear_input(self):
        """Clear the QR input field"""
        self.qr_var.set("")
        self.qr_entry.focus_set()
        self.job_type_var.set("None")
        self.job_url_var.set("None")
        self.update_status("Input cleared - ready for next scan", 'blue')
    
    def process_qr_input(self):
        """Process the QR input and start printing"""
        qr_data = self.qr_var.get().strip()
        if not qr_data:
            self.update_status("Please scan or enter QR code data", 'red', auto_reset=True)
            return
        
        self.log(f"Processing QR: {qr_data}")
        
        try:
            separator = self.config["settings"].get("qr_separator", ":")
            if separator in qr_data and qr_data.count(separator) >= 1:
                parts = qr_data.split(separator, 1)
                if len(parts) == 2:
                    prefix, url = parts
                    printer_type_id = self.get_printer_type_by_prefix(prefix.lower())
                    
                    if printer_type_id:
                        type_config = self.config["printer_types"][printer_type_id]
                        self.log(f"Valid {type_config['display_name']} print request detected")
                        
                        # Save to history first
                        self.save_to_history(url, printer_type_id, qr_data)
                        
                        # Update status and start printing
                        self.update_status(f"Processing {type_config['display_name']} print...", 'orange')
                        
                        # Start printing in background thread
                        threading.Thread(target=self.download_and_print, 
                                       args=(url, printer_type_id), daemon=True).start()
                        
                        # Clear input if auto-print is enabled
                        if self.auto_print_var.get():
                            self.root.after(2000, self.clear_input)  # Clear after 2 seconds
                        
                        return
                    else:
                        valid_prefixes = self.get_valid_prefixes()
                        error_msg = f"Unknown prefix: '{prefix}'. Valid prefixes: {', '.join(valid_prefixes)}"
                        self.log(error_msg)
                        self.update_status(error_msg, 'red', auto_reset=True)
                        return
            
            # Invalid format
            valid_prefixes = self.get_valid_prefixes()
            separator = self.config["settings"].get("qr_separator", ":")
            error_msg = f"Invalid QR format. Expected: 'prefix{separator}url' (e.g., '{valid_prefixes[0]}{separator}https://example.com/file.pdf')"
            self.log(error_msg)
            self.update_status(error_msg, 'red', auto_reset=True)
            
        except Exception as e:
            error_msg = f"QR processing error: {str(e)}"
            self.log(error_msg)
            self.update_status(error_msg, 'red', auto_reset=True)
    
    def save_to_history(self, url, print_type, qr_data):
        """Save print job to history"""
        try:
            self.db_manager.insert('''
                INSERT INTO print_history (url, print_type, qr_data, status)
                VALUES (?, ?, ?, ?)
            ''', (url, print_type, qr_data, 'processing'))
            self.root.after(0, self.refresh_history)
        except Exception as e:
            self.log(f"Error saving to history: {e}")
    
    def download_and_print(self, url, print_type):
        """Download PDF and send to printer"""
        temp_file = None
        try:
            self.root.after(0, lambda: self.log(f"Downloading: {url}"))
            
            # Download PDF
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Check if it's actually a PDF
            content_type = response.headers.get('Content-Type', '')
            if 'application/pdf' not in content_type and not url.lower().endswith('.pdf'):
                raise Exception(f"URL does not return a PDF file (Content-Type: {content_type})")
            
            # Create temp file
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, f"qr_print_{uuid.uuid4().hex}.pdf")
            
            # Save PDF
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.root.after(0, lambda: self.log(f"Download complete. Sending to {print_type} printer..."))
            self.root.after(0, lambda: self.update_status(f"Printing {print_type}...", 'orange'))
            
            # Send to printer
            success = self.send_to_printer(temp_file, print_type)
            
            if success:
                self.root.after(0, lambda: self.log(f"✓ {print_type.title()} printed successfully"))
                self.root.after(0, lambda: self.update_status(f"✓ {print_type.title()} printed successfully!", 'green'))
                self.update_history_status(url, 'completed')
            else:
                self.root.after(0, lambda: self.log(f"✗ {print_type.title()} print failed"))
                self.root.after(0, lambda: self.update_status(f"✗ Print failed. Check printer connection.", 'red', auto_reset=True))
                self.update_history_status(url, 'failed')
                
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: self.log(f"Print error: {error_msg}"))
            self.root.after(0, lambda: self.update_status(f"Print error: {error_msg}", 'red', auto_reset=True))
            self.update_history_status(url, 'error')
        finally:
            # Clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
    
    def update_history_status(self, url, status):
        """Update the status of the most recent matching URL in history"""
        try:
            self.db_manager.update('''
                UPDATE print_history 
                SET status = ? 
                WHERE url = ? 
                AND id = (
                    SELECT id FROM print_history 
                    WHERE url = ? 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                )
            ''', (status, url, url))
            self.root.after(0, self.refresh_history)
        except Exception as e:
            self.log(f"Error updating history status: {e}")
    
    def send_to_printer(self, file_path, printer_type_id):
        """Send file to printer based on printer type and configuration"""
        try:
            system = platform.system()
            printer_config = self.config['printer_types'][printer_type_id]
            printer_name = printer_config['printer_name']
            printer_options = printer_config.get('options', [])
            
            self.log(f"Sending to {printer_config['display_name']}: {printer_name}")
            
            if system == "Windows":
                if printer_name == "default":
                    # Use default printer
                    os.startfile(file_path, "print")
                else:
                    # Print to specific printer using PowerShell
                    ps_script = f'''
                    $printer = "{printer_name}"
                    $file = "{file_path}"
                    Start-Process -FilePath $file -Verb PrintTo -ArgumentList $printer -Wait
                    '''
                    subprocess.run(["powershell", "-Command", ps_script], check=True)
                return True
                
            elif system == "Darwin":  # macOS
                cmd = ["lpr"]
                
                if printer_name != "default":
                    cmd.extend(["-P", printer_name])
                
                # Add printer-specific options
                for option in printer_options:
                    cmd.extend(["-o", option])
                
                # Add media selection only if not auto
                media_setting = printer_config.get('media', 'auto (printer default)')
                if not media_setting.startswith('auto'):
                    cmd.extend(["-o", f"media={media_setting}"])
                # If auto, don't add any media parameter - use printer default
                
                cmd.append(file_path)
                subprocess.run(cmd, check=True)
                return True
                
            elif system == "Linux":
                cmd = ["lp"]
                
                if printer_name != "default":
                    cmd.extend(["-d", printer_name])
                
                # Add printer-specific options
                for option in printer_options:
                    cmd.extend(["-o", option])
                
                # Add media selection only if not auto
                media_setting = printer_config.get('media', 'auto (printer default)')
                if not media_setting.startswith('auto'):
                    cmd.extend(["-o", f"media={media_setting}"])
                # If auto, don't add any media parameter - use printer default
                
                cmd.append(file_path)
                subprocess.run(cmd, check=True)
                return True
                
            else:
                error_msg = f"Printing not supported on {system}"
                self.root.after(0, lambda: self.log(error_msg))
                self.root.after(0, lambda: self.update_status(error_msg, 'red', auto_reset=True))
                return False
                
        except subprocess.CalledProcessError as e:
            error_msg = f"Printer command failed: {str(e)}"
            if "No such printer" in str(e) or "unknown printer" in str(e).lower():
                error_msg = f"Printer '{printer_name}' not found. Please check printer configuration."
            self.root.after(0, lambda: self.log(error_msg))
            return False
        except Exception as e:
            error_msg = f"Printer error: {str(e)}"
            self.root.after(0, lambda: self.log(error_msg))
            return False
    
    def refresh_history(self):
        """Refresh the history treeview"""
        try:
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)
            
            rows = self.db_manager.select('''
                SELECT id, print_type, url, status, timestamp 
                FROM print_history 
                ORDER BY timestamp DESC
                LIMIT 100
            ''')
            
            for row in rows:
                id_, print_type, url, status, timestamp = row
                # Format timestamp
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00')) if 'Z' in timestamp else datetime.fromisoformat(timestamp)
                    formatted_time = dt.strftime("%m/%d %H:%M")
                except:
                    formatted_time = timestamp[:16] if len(timestamp) > 16 else timestamp
                
                # Truncate URL for display
                display_url = url if len(url) <= 50 else url[:47] + "..."
                
                # Status color coding
                status_display = status
                if status == 'completed':
                    status_display = '✓ Done'
                elif status == 'failed' or status == 'error':
                    status_display = '✗ Failed'
                elif status == 'processing':
                    status_display = '⏳ Processing'
                
                self.history_tree.insert('', 'end', values=(print_type.upper(), display_url, status_display, formatted_time), tags=(str(id_),))
        except Exception as e:
            self.log(f"Error refreshing history: {e}")
    
    def get_selected_item(self):
        """Get selected item from history"""
        selection = self.history_tree.selection()
        if not selection:
            self.log("Please select an item from history")
            self.update_status("Please select an item from history", 'red', auto_reset=True)
            return None
        
        item = selection[0]
        item_id = self.history_tree.item(item, 'tags')[0]
        
        try:
            result = self.db_manager.select_one('SELECT url, print_type, qr_data FROM print_history WHERE id = ?', (item_id,))
            
            if result:
                return {'id': item_id, 'url': result[0], 'print_type': result[1], 'qr_data': result[2]}
            return None
        except Exception as e:
            self.log(f"Error getting selected item: {e}")
            return None
    
    def reprint_selected(self):
        """Reprint the selected item"""
        item = self.get_selected_item()
        if not item:
            return
        
        self.log(f"Reprinting: {item['print_type']} - {item['url']}")
        self.update_status(f"Reprinting {item['print_type']}...", 'orange')
        threading.Thread(target=self.download_and_print, 
                        args=(item['url'], item['print_type']), daemon=True).start()
    
    def delete_selected(self):
        """Delete selected item from history"""
        item = self.get_selected_item()
        if not item:
            return
        
        if messagebox.askyesno("Confirm Delete", "Delete selected item from history?"):
            try:
                self.db_manager.delete('DELETE FROM print_history WHERE id = ?', (item['id'],))
                self.refresh_history()
                self.log("History item deleted")
            except Exception as e:
                self.log(f"Error deleting history item: {e}")
    
    def clear_history(self):
        """Clear all history"""
        if messagebox.askyesno("Confirm Clear", "Clear all print history?"):
            try:
                self.db_manager.delete('DELETE FROM print_history', ())
                self.refresh_history()
                self.log("All history cleared")
            except Exception as e:
                self.log(f"Error clearing history: {e}")
    
    def on_history_double_click(self, event):
        """Handle double-click on history item"""
        self.reprint_selected()
    
    def on_closing(self):
        """Handle window closing"""
        if hasattr(self, 'db_manager'):
            self.db_manager.close()
        
        self.root.destroy()

class PrinterTypeDialog:
    """Dialog for adding a new printer type"""
    
    def __init__(self, parent, app):
        self.app = app
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add Printer Type")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
        
        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill='both', expand=True)
        
        # Type ID
        ttk.Label(main_frame, text="Type ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.type_id_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.type_id_var, width=30).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Display Name
        ttk.Label(main_frame, text="Display Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.display_name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.display_name_var, width=30).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Prefix
        ttk.Label(main_frame, text="QR Prefix:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.prefix_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.prefix_var, width=30).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Media Options
        ttk.Label(main_frame, text="Media Options:").grid(row=3, column=0, sticky=(tk.W, tk.N), pady=5)
        self.media_text = tk.Text(main_frame, height=8, width=40)
        self.media_text.grid(row=3, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # Default media options
        default_media = "auto (printer default)\nCustom.4x6in\nCustom.2x1in"
        self.media_text.insert(tk.END, default_media)
        
        ttk.Label(main_frame, text="(One option per line)", font=('TkDefaultFont', 8)).grid(row=4, column=1, sticky=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="OK", command=self.ok_clicked).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.cancel_clicked).pack(side=tk.LEFT)
        
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
    
    def ok_clicked(self):
        type_id = self.type_id_var.get().strip()
        display_name = self.display_name_var.get().strip()
        prefix = self.prefix_var.get().strip()
        media_options = [line.strip() for line in self.media_text.get("1.0", tk.END).split('\n') if line.strip()]
        
        if not type_id or not display_name or not prefix:
            # For dialog boxes, we can't use the main app's status, so we'll keep minimal error handling here
            # This dialog will close and the user can try again
            self.app.log("Please fill in all required fields!")
            self.app.update_status("Please fill in all required fields!", 'red', auto_reset=True)
            return
        
        if not media_options:
            media_options = ["auto (printer default)"]
        
        self.result = (type_id, display_name, prefix, media_options)
        self.dialog.destroy()
    
    def cancel_clicked(self):
        self.dialog.destroy()

class PrinterTypeSelectionDialog:
    """Dialog for selecting a printer type to remove"""
    
    def __init__(self, parent, printer_types):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Printer Type to Remove")
        self.dialog.geometry("300x200")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
        
        self.create_widgets(printer_types)
    
    def create_widgets(self, printer_types):
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Select printer type to remove:").pack(pady=(0, 10))
        
        self.selected_type = tk.StringVar()
        for ptype in printer_types:
            ttk.Radiobutton(main_frame, text=ptype, variable=self.selected_type, value=ptype).pack(anchor=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Remove", command=self.ok_clicked).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.cancel_clicked).pack(side=tk.LEFT)
    
    def ok_clicked(self):
        if self.selected_type.get():
            self.result = self.selected_type.get()
        self.dialog.destroy()
    
    def cancel_clicked(self):
        self.dialog.destroy()

def main():
    root = tk.Tk()
    app = QRPDFPrinter(root)
    
    # Set window icon if available
    try:
        root.iconbitmap('printer.ico')  # Add your icon file
    except:
        pass
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()