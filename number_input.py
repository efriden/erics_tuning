import tkinter as tk
from tkinter import ttk
import re
import threading
import time

# Global variables to store the input values
value1 = 0.0
value2 = 0.0

# Flag to check if the GUI is running
is_running = False

class NumberInputApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Number Input")
        self.root.geometry("300x150")
        self.root.resizable(False, False)
        
        # Configure styles
        self.style = ttk.Style()
        self.style.configure('TLabel', font=('Arial', 11))
        self.style.configure('TEntry', font=('Arial', 11))
        
        # Create a frame for the first input
        self.frame1 = ttk.Frame(root, padding="10 10 10 0")
        self.frame1.pack(fill=tk.X)
        
        # Label and entry for the first value
        self.label1 = ttk.Label(self.frame1, text="Number 1:")
        self.label1.pack(side=tk.LEFT, padx=(0, 10))
        
        self.value1_var = tk.StringVar(value="20.0")
        self.value1_var.trace_add("write", self.validate_and_update_value1)
        self.entry1 = ttk.Entry(self.frame1, textvariable=self.value1_var, width=15)
        self.entry1.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Create a frame for the second input
        self.frame2 = ttk.Frame(root, padding="10 10 10 0")
        self.frame2.pack(fill=tk.X)
        
        # Label and entry for the second value
        self.label2 = ttk.Label(self.frame2, text="Number 2:")
        self.label2.pack(side=tk.LEFT, padx=(0, 10))
        
        self.value2_var = tk.StringVar(value="5000.0")
        self.value2_var.trace_add("write", self.validate_and_update_value2)
        self.entry2 = ttk.Entry(self.frame2, textvariable=self.value2_var, width=15)
        self.entry2.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Status label
        self.status_frame = ttk.Frame(root, padding="10 10 10 10")
        self.status_frame.pack(fill=tk.X)
        
        self.status_var = tk.StringVar(value="Status: Ready")
        self.status_label = ttk.Label(self.status_frame, textvariable=self.status_var)
        self.status_label.pack(side=tk.LEFT)
        
        # Set the protocol for when the window is closed
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Set the initial values
        global value1, value2
        value1 = 20.0
        value2 = 5000.0
    
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
                value1 = float(text) if text else 0.0
                self.status_var.set(f"Status: Values updated - Number 1: {value1}, Number 2: {value2}")
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
                value2 = float(text) if text else 0.0
                self.status_var.set(f"Status: Values updated - Number 1: {value1}, Number 2: {value2}")
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

