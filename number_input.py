import tkinter as tk
from tkinter import ttk
import re
import threading
import time

# Global variables to store the input values
value1 = 0.0
value2 = 0.0
beat_detection_enabled = True  # Global beat detection control

# Flag to check if the GUI is running
is_running = False

class NumberInputApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Piano Tuning Frequency Range")
        self.root.geometry("450x400")
        self.root.resizable(True, True)
        
        # Define frequency range presets
        self.presets = {
            "Full Range": (20.0, 5000.0),
            "Piano Full": (25.0, 4500.0),
            "Bass Register": (25.0, 300.0),
            "Middle Register": (120.0, 1200.0),
            "Treble Register": (400.0, 5000.0),
            "A440 Focus": (420.0, 460.0),
            "Temperament": (200.0, 800.0),
            "Low Bass (A0-C2)": (25.0, 80.0),
            "Mid Bass (C2-C4)": (80.0, 300.0),
            "Tenor (C3-C5)": (250.0, 550.0),
            "Soprano (C4-C6)": (250.0, 1100.0),
            "High Treble (C6-C8)": (1000.0, 4500.0),
            "Beat Detection": (100.0, 1000.0),
            "Octave Check": (200.0, 900.0),
            "Unison Tuning": (80.0, 2000.0),
            "Quiet Room": (20.0, 8000.0),
            "Noisy Environment": (100.0, 2000.0),
            "Outdoor Tuning": (50.0, 3000.0),
            # Beat Detection Specific Presets
            "Perfect 5th (Bass)": (80.0, 250.0),
            "Perfect 5th (Middle)": (200.0, 800.0),
            "Perfect 5th (Treble)": (400.0, 1500.0),
            "Octave Beats (Bass)": (50.0, 200.0),
            "Octave Beats (Middle)": (150.0, 600.0),
            "Octave Beats (Treble)": (300.0, 1200.0),
            "Unison Strings (Bass)": (80.0, 150.0),
            "Unison Strings (Tenor)": (150.0, 350.0),
            "Unison Strings (Alto)": (250.0, 500.0),
            "4th & 5th Intervals": (150.0, 700.0),
            "Major 3rd Beats": (200.0, 600.0),
            "Temperament Beats": (180.0, 900.0)
        }
        
        # Configure styles
        self.style = ttk.Style()
        self.style.configure('TLabel', font=('Arial', 10))
        self.style.configure('TEntry', font=('Arial', 10))
        self.style.configure('Preset.TButton', font=('Arial', 8), padding=2)
        
        # Create main container with scrollable frame
        main_frame = ttk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Manual input section
        input_frame = ttk.LabelFrame(main_frame, text="Manual Frequency Range (Hz)", padding=10)
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        # First row: Min frequency
        row1 = ttk.Frame(input_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="Min Freq (Hz):", width=12).pack(side=tk.LEFT)
        self.value1_var = tk.StringVar(value="20.0")
        self.value1_var.trace_add("write", self.validate_and_update_value1)
        self.entry1 = ttk.Entry(row1, textvariable=self.value1_var, width=10)
        self.entry1.pack(side=tk.LEFT, padx=(5, 10))
        
        # Second row: Max frequency  
        row2 = ttk.Frame(input_frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="Max Freq (Hz):", width=12).pack(side=tk.LEFT)
        self.value2_var = tk.StringVar(value="5000.0")
        self.value2_var.trace_add("write", self.validate_and_update_value2)
        self.entry2 = ttk.Entry(row2, textvariable=self.value2_var, width=10)
        self.entry2.pack(side=tk.LEFT, padx=(5, 10))
        
        # Current range display
        self.current_range_var = tk.StringVar(value="Current: 20.0 - 5000.0 Hz")
        current_label = ttk.Label(input_frame, textvariable=self.current_range_var, font=('Arial', 9, 'bold'))
        current_label.pack(pady=(5, 0))
        
        # Beat detection control
        beat_control_frame = ttk.Frame(input_frame)
        beat_control_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.beat_detection_var = tk.BooleanVar(value=True)
        self.beat_detection_var.trace_add("write", self.toggle_beat_detection)
        beat_checkbox = ttk.Checkbutton(
            beat_control_frame, 
            text="Enable Beat Detection", 
            variable=self.beat_detection_var
        )
        beat_checkbox.pack(side=tk.LEFT)
        
        # Beat detection status
        self.beat_status_var = tk.StringVar(value="Beat Detection: ON")
        beat_status_label = ttk.Label(
            beat_control_frame, 
            textvariable=self.beat_status_var, 
            font=('Arial', 8), 
            foreground='green'
        )
        beat_status_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Preset buttons section
        preset_frame = ttk.LabelFrame(main_frame, text="Quick Presets", padding=10)
        preset_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create preset buttons in categories
        self.create_preset_buttons(preset_frame)
        
        # Status label
        self.status_var = tk.StringVar(value="Status: Ready - Select a preset or enter custom range")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, font=('Arial', 8))
        status_label.pack(fill=tk.X, pady=(5, 0))
        
        # Set the protocol for when the window is closed
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Set the initial values
        global value1, value2
        value1 = 20.0
        value2 = 5000.0
    
    def create_preset_buttons(self, parent):
        """Create categorized preset buttons"""
        
        # Define categories for better organization
        categories = {
            "General": ["Full Range", "Piano Full", "Quiet Room", "Noisy Environment", "Outdoor Tuning"],
            "Piano Registers": ["Bass Register", "Middle Register", "Treble Register", "Low Bass (A0-C2)", "Mid Bass (C2-C4)"],
            "Vocal Ranges": ["Tenor (C3-C5)", "Soprano (C4-C6)", "High Treble (C6-C8)"],
            "Tuning Techniques": ["A440 Focus", "Temperament", "Beat Detection", "Octave Check", "Unison Tuning"],
            "Beat Detection - Intervals": ["Perfect 5th (Bass)", "Perfect 5th (Middle)", "Perfect 5th (Treble)", "4th & 5th Intervals", "Major 3rd Beats", "Temperament Beats"],
            "Beat Detection - Octaves": ["Octave Beats (Bass)", "Octave Beats (Middle)", "Octave Beats (Treble)"],
            "Beat Detection - Unisons": ["Unison Strings (Bass)", "Unison Strings (Tenor)", "Unison Strings (Alto)"]
        }
        
        for category, preset_names in categories.items():
            # Create category frame
            cat_frame = ttk.LabelFrame(parent, text=category, padding=5)
            cat_frame.pack(fill=tk.X, pady=2)
            
            # Create buttons in rows of 2-3
            button_frame = ttk.Frame(cat_frame)
            button_frame.pack(fill=tk.X)
            
            for i, preset_name in enumerate(preset_names):
                if preset_name in self.presets:
                    fmin, fmax = self.presets[preset_name]
                    btn = ttk.Button(
                        button_frame,
                        text=f"{preset_name}\n({fmin:.0f}-{fmax:.0f} Hz)",
                        style='Preset.TButton',
                        command=lambda p=preset_name: self.apply_preset(p),
                        width=20
                    )
                    # Arrange in grid: 2 buttons per row for most categories
                    row = i // 2
                    col = i % 2
                    btn.grid(row=row, column=col, padx=2, pady=1, sticky='ew')
            
            # Configure column weights for equal distribution
            button_frame.columnconfigure(0, weight=1)
            button_frame.columnconfigure(1, weight=1)
    
    def apply_preset(self, preset_name):
        """Apply a preset frequency range"""
        if preset_name in self.presets:
            fmin, fmax = self.presets[preset_name]
            self.value1_var.set(str(fmin))
            self.value2_var.set(str(fmax))
            global value1, value2
            value1 = fmin
            value2 = fmax
            self.update_display()
            self.status_var.set(f"Applied preset: {preset_name} ({fmin:.0f}-{fmax:.0f} Hz)")
    
    def update_display(self):
        """Update the current range display"""
        global value1, value2
        self.current_range_var.set(f"Current: {value1:.1f} - {value2:.1f} Hz")
    
    def toggle_beat_detection(self, *args):
        """Toggle beat detection on/off"""
        global beat_detection_enabled
        beat_detection_enabled = self.beat_detection_var.get()
        
        if beat_detection_enabled:
            self.beat_status_var.set("Beat Detection: ON")
            # Update status label to green
            for widget in self.root.winfo_children():
                self._update_beat_status_color(widget, 'green')
        else:
            self.beat_status_var.set("Beat Detection: OFF")
            # Update status label to red
            for widget in self.root.winfo_children():
                self._update_beat_status_color(widget, 'red')
        
        self.status_var.set(f"Beat detection {'enabled' if beat_detection_enabled else 'disabled'}")
    
    def _update_beat_status_color(self, widget, color):
        """Helper to update beat status label color recursively"""
        try:
            if hasattr(widget, 'cget') and widget.cget('text') and 'Beat Detection:' in str(widget.cget('text')):
                widget.configure(foreground=color)
        except:
            pass
        
        # Recursively check children
        for child in widget.winfo_children():
            self._update_beat_status_color(child, color)
    
    def validate_and_update_value1(self, *args):
        """Validate input for the first entry and update the global value."""
        global value1
        try:
            # Get the current value from the entry
            text = self.value1_var.get()
            
            # Skip if empty
            if not text:
                return
            
            # Check if the input is a valid number format
            if re.match(r'^-?\d*\.?\d*$', text) and text not in ['-', '.', '-.']:
                # Update the global value
                new_value = float(text) if text else 0.0
                if new_value >= 0:  # Frequency must be positive
                    value1 = new_value
                    self.update_display()
                    self.status_var.set(f"Min frequency updated: {value1:.1f} Hz")
                else:
                    self.value1_var.set(str(value1))
            else:
                # Revert to the previous valid value
                self.value1_var.set(str(value1))
        except Exception as e:
            # If there's any error, revert to the previous valid value
            self.value1_var.set(str(value1))
    
    def validate_and_update_value2(self, *args):
        """Validate input for the second entry and update the global value."""
        global value2
        try:
            # Get the current value from the entry
            text = self.value2_var.get()
            
            # Skip if empty
            if not text:
                return
            
            # Check if the input is a valid number format
            if re.match(r'^-?\d*\.?\d*$', text) and text not in ['-', '.', '-.']:
                # Update the global value
                new_value = float(text) if text else 0.0
                if new_value >= 0:  # Frequency must be positive
                    value2 = new_value
                    self.update_display()
                    global value1
                    if value2 <= value1:
                        self.status_var.set(f"Warning: Max freq ({value2:.1f}) should be > Min freq ({value1:.1f})")
                    else:
                        self.status_var.set(f"Max frequency updated: {value2:.1f} Hz")
                else:
                    self.value2_var.set(str(value2))
            else:
                # Revert to the previous valid value
                self.value2_var.set(str(value2))
        except Exception as e:
            # If there's any error, revert to the previous valid value
            self.value2_var.set(str(value2))
    
    def on_closing(self):
        """Handle the window closing event."""
        global is_running
        is_running = False
        self.root.destroy()

def get_value1():
    """Get the current value of Number 1."""
    global value1
    return value1

def get_value2():
    """Get the current value of Number 2."""
    global value2
    return value2

def get_beat_detection_enabled():
    """Get the current beat detection enabled state."""
    global beat_detection_enabled
    return beat_detection_enabled

def start_gui_thread():
    """Start the GUI in a separate thread."""
    global is_running
    
    # Don't start if already running
    if is_running:
        return
    
    is_running = True
    
    def run_gui():
        root = tk.Tk()
        app = NumberInputApp(root)
        root.mainloop()
    
    gui_thread = threading.Thread(target=run_gui)
    gui_thread.daemon = True  # Thread will close when main program exits
    gui_thread.start()

def start_gui():
    """Start the GUI in a blocking way (for direct usage)."""
    global is_running
    
    # Don't start if already running
    if is_running:
        return
    
    is_running = True
    root = tk.Tk()
    app = NumberInputApp(root)
    root.mainloop()

# Example usage:
if __name__ == "__main__":
    # Start the GUI directly when this file is run
    start_gui()

