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
from datetime import datetime

class QRPDFPrinter:
    def __init__(self, root):
        self.root = root
        self.root.title("QR PDF Printer")
        self.root.geometry("700x650")
        
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
        
    def get_media_options(self, print_type):
        """Get available media options for a print type"""
        if print_type == 'label':
            return [
                'auto (printer default)',
                'Custom.2x1in',
                'Custom.4x6in', 
                'Custom.51x25mm',
                'Custom.102x51mm',
                'Custom.4x2in',
                'Custom.3x1in',
                'Custom.62x29mm',
                'na_index-4x6_4x6in',
                'om_small-photo_100x150mm'
            ]
        elif print_type == 'receipt':
            return [
                'auto (printer default)',
                'Receipt',
                'Custom.3x11in',
                'Custom.80mm',
                'Custom.58mm',
                'Custom.57x32000mm',
                'Custom.80x200mm'
            ]
        return ['auto (printer default)']
    
    def load_config(self):
        """Load printer configuration from JSON file"""
        self.config_file = "printer_config.json"
        
        # Default configuration
        self.config = {
            "printers": {
                "label": {
                    "name": "default",
                    "media": "auto (printer default)",
                    "options": []
                },
                "receipt": {
                    "name": "default",
                    "media": "auto (printer default)",
                    "options": []
                }
            },
            "settings": {
                "auto_print": True,
                "auto_clear": True,
                "timeout": 30
            }
        }
        
        # Load config file if it exists
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    self.config.update(loaded_config)
                print(f"Configuration loaded from {self.config_file}")
            except Exception as e:
                print(f"Error loading config: {e}")
                messagebox.showwarning("Config Warning", 
                    f"Could not load config file: {e}\nUsing default settings.")
        else:
            # Create default config file
            self.save_config()
            print(f"Created default configuration file: {self.config_file}")
    
    def save_config(self):
        """Save current configuration to JSON file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            messagebox.showerror("Config Error", f"Could not save config: {e}")
    
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
        """Initialize SQLite database for print history"""
        self.conn = sqlite3.connect('printer_history.db')
        cursor = self.conn.cursor()
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
        self.conn.commit()
    
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
        config_frame.columnconfigure(1, weight=1)
        config_frame.columnconfigure(3, weight=1)
        
        # Label printer
        ttk.Label(config_frame, text="Label Printer:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.label_printer_var = tk.StringVar(value=self.config['printers']['label']['name'])
        label_combo = ttk.Combobox(config_frame, textvariable=self.label_printer_var, width=25)
        label_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        
        ttk.Label(config_frame, text="Media:").grid(row=0, column=2, sticky=tk.W, padx=(5, 5))
        self.label_media_var = tk.StringVar(value=self.config['printers']['label'].get('media', 'auto'))
        label_media_combo = ttk.Combobox(config_frame, textvariable=self.label_media_var, width=20)
        label_media_combo['values'] = self.get_media_options('label')
        label_media_combo.grid(row=0, column=3, sticky=(tk.W, tk.E), padx=(0, 5))
        
        # Receipt printer  
        ttk.Label(config_frame, text="Receipt Printer:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.receipt_printer_var = tk.StringVar(value=self.config['printers']['receipt']['name'])
        receipt_combo = ttk.Combobox(config_frame, textvariable=self.receipt_printer_var, width=25)
        receipt_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        
        ttk.Label(config_frame, text="Media:").grid(row=1, column=2, sticky=tk.W, padx=(5, 5))
        self.receipt_media_var = tk.StringVar(value=self.config['printers']['receipt'].get('media', 'auto'))
        receipt_media_combo = ttk.Combobox(config_frame, textvariable=self.receipt_media_var, width=20)
        receipt_media_combo['values'] = self.get_media_options('receipt')
        receipt_media_combo.grid(row=1, column=3, sticky=(tk.W, tk.E), padx=(0, 5))
        
        # Populate printer dropdowns
        available_printers = ['default'] + self.get_available_printers()
        label_combo['values'] = available_printers
        receipt_combo['values'] = available_printers
        
        # Config buttons
        config_btn_frame = ttk.Frame(config_frame)
        config_btn_frame.grid(row=0, column=4, rowspan=2, padx=(5, 0))
        
        ttk.Button(config_btn_frame, text="Refresh\nPrinters", 
                  command=lambda: self.refresh_printer_list(label_combo, receipt_combo)).pack(pady=(0, 5))
        ttk.Button(config_btn_frame, text="Save\nConfig", 
                  command=self.save_printer_config).pack()
        
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
    
    def refresh_printer_list(self, label_combo, receipt_combo):
        """Refresh the list of available printers"""
        available_printers = ['default'] + self.get_available_printers()
        label_combo['values'] = available_printers
        receipt_combo['values'] = available_printers
        self.log("Printer list refreshed")
    
    def save_printer_config(self):
        """Save current printer configuration"""
        self.config['printers']['label']['name'] = self.label_printer_var.get()
        self.config['printers']['label']['media'] = self.label_media_var.get()
        self.config['printers']['receipt']['name'] = self.receipt_printer_var.get()
        self.config['printers']['receipt']['media'] = self.receipt_media_var.get()
        self.config['settings']['auto_print'] = self.auto_print_var.get()
        
        self.save_config()
        self.log("Printer configuration saved")
        messagebox.showinfo("Config Saved", "Printer configuration has been saved!")
    
    def update_status(self, message, color='blue'):
        """Update status label"""
        self.status_var.set(message)
        self.status_label.configure(foreground=color)
    
    def on_qr_input_change(self, event):
        """Handle changes in QR input field"""
        qr_data = self.qr_var.get().strip()
        if qr_data:
            self.process_btn.configure(state='normal')
            # Try to parse and show preview
            try:
                if ':' in qr_data and qr_data.count(':') >= 1:
                    parts = qr_data.split(':', 1)
                    if len(parts) == 2:
                        print_type, url = parts
                        if print_type.lower() in ['label', 'receipt']:
                            self.job_type_var.set(print_type.upper())
                            display_url = url if len(url) <= 60 else url[:57] + "..."
                            self.job_url_var.set(display_url)
                            self.update_status(f"Ready to print {print_type} - Press Enter or click Process", 'green')
                            return
                
                self.job_type_var.set("Invalid Format")
                self.job_url_var.set("Expected: type:url")
                self.update_status("Invalid QR format. Expected: 'label:url' or 'receipt:url'", 'red')
                
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
            messagebox.showwarning("Warning", "Please scan or enter QR code data")
            return
        
        self.log(f"Processing QR: {qr_data}")
        
        try:
            # Parse QR data format: "type:url"
            if ':' in qr_data and qr_data.count(':') >= 1:
                parts = qr_data.split(':', 1)
                if len(parts) == 2:
                    print_type, url = parts
                    
                    # Validate print type
                    if print_type.lower() in ['label', 'receipt']:
                        self.log(f"Valid {print_type} print request detected")
                        
                        # Save to history first
                        self.save_to_history(url, print_type.lower(), qr_data)
                        
                        # Update status and start printing
                        self.update_status(f"Processing {print_type} print...", 'orange')
                        
                        # Start printing in background thread
                        threading.Thread(target=self.download_and_print, 
                                       args=(url, print_type.lower()), daemon=True).start()
                        
                        # Clear input if auto-print is enabled
                        if self.auto_print_var.get():
                            self.root.after(2000, self.clear_input)  # Clear after 2 seconds
                        
                        return
                    else:
                        error_msg = f"Unknown print type: '{print_type}'. Expected 'label' or 'receipt'"
                        self.log(error_msg)
                        self.update_status(error_msg, 'red')
                        messagebox.showerror("Invalid QR Code", error_msg)
                        return
            
            # Invalid format
            error_msg = "Invalid QR format. Expected: 'type:url' (e.g., 'label:https://example.com/file.pdf')"
            self.log(error_msg)
            self.update_status(error_msg, 'red')
            messagebox.showerror("Invalid QR Code", error_msg)
            
        except Exception as e:
            error_msg = f"QR processing error: {str(e)}"
            self.log(error_msg)
            self.update_status(error_msg, 'red')
            messagebox.showerror("QR Error", error_msg)
    
    def save_to_history(self, url, print_type, qr_data):
        """Save print job to history"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO print_history (url, print_type, qr_data, status)
            VALUES (?, ?, ?, ?)
        ''', (url, print_type, qr_data, 'processing'))
        self.conn.commit()
        self.root.after(0, self.refresh_history)
    
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
                self.root.after(0, lambda: self.update_status(f"✗ Print failed. Check printer connection.", 'red'))
                self.update_history_status(url, 'failed')
                
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: self.log(f"Print error: {error_msg}"))
            self.root.after(0, lambda: self.update_status(f"Print error: {error_msg}", 'red'))
            self.root.after(0, lambda: messagebox.showerror("Print Error", f"Failed to print: {error_msg}"))
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
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE print_history 
            SET status = ? 
            WHERE url = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
        ''', (status, url))
        self.conn.commit()
        self.root.after(0, self.refresh_history)
    
    def send_to_printer(self, file_path, print_type):
        """Send file to printer based on print type and configuration"""
        try:
            system = platform.system()
            printer_config = self.config['printers'][print_type]
            printer_name = printer_config['name']
            printer_options = printer_config.get('options', [])
            
            self.log(f"Sending to {print_type} printer: {printer_name}")
            
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
                media_setting = self.config['printers'][print_type].get('media', 'auto (printer default)')
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
                media_setting = self.config['printers'][print_type].get('media', 'auto (printer default)')
                if not media_setting.startswith('auto'):
                    cmd.extend(["-o", f"media={media_setting}"])
                # If auto, don't add any media parameter - use printer default
                
                cmd.append(file_path)
                subprocess.run(cmd, check=True)
                return True
                
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Printing not supported on {system}"))
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
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, print_type, url, status, timestamp 
            FROM print_history 
            ORDER BY timestamp DESC
            LIMIT 100
        ''')
        
        for row in cursor.fetchall():
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
    
    def get_selected_item(self):
        """Get selected item from history"""
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an item from history")
            return None
        
        item = selection[0]
        item_id = self.history_tree.item(item, 'tags')[0]
        
        cursor = self.conn.cursor()
        cursor.execute('SELECT url, print_type, qr_data FROM print_history WHERE id = ?', (item_id,))
        result = cursor.fetchone()
        
        if result:
            return {'id': item_id, 'url': result[0], 'print_type': result[1], 'qr_data': result[2]}
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
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM print_history WHERE id = ?', (item['id'],))
            self.conn.commit()
            self.refresh_history()
            self.log("History item deleted")
    
    def clear_history(self):
        """Clear all history"""
        if messagebox.askyesno("Confirm Clear", "Clear all print history?"):
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM print_history')
            self.conn.commit()
            self.refresh_history()
            self.log("All history cleared")
    
    def on_history_double_click(self, event):
        """Handle double-click on history item"""
        self.reprint_selected()
    
    def on_closing(self):
        """Handle window closing"""
        if hasattr(self, 'conn'):
            self.conn.close()
        
        self.root.destroy()

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