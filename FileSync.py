''''

    Updates:
        CRITICAL TO CONVERT TO EXE: PLACE MEMORY DIR ('data') WITHIN A READ/WRITE DIR , LIKE '/ProgramFiles/'
        1. deselection of a task item when the user clicks anywhere else
        2. make sure auto-sync works, and add a 1m interval
        3. modify verbros setup:
            a. Normal (renamed from status change}: status changes, including proceeses starting, finshed, and some stats, like files chacked, or files coppied, filed deleted.
            b. Hyper-Log: as is, but make sure in include every Normal does, on top of individule processes, and a metrics table at the end of the sync job
            c. Clean: as is
        4. Round the progress percentage to 0.x (tenths)
        5. add a graphical loding bar to the right of the % of progress.

'''

import sys, os, shutil, threading, time, json, logging
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
from colorama import Fore, Style
from PIL import Image, ImageTk

class DirectorySyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Directory Sync Tool")
        self.root.geometry("1080x740")

        # Define the custom ProgramFiles directory
        exe_dir = os.path.join(Path.home(), "Desktop")  # Get the user's Desktop directory
        custom_program_files_dir = os.path.join(exe_dir, "Custom ProgramFiles")
        if not os.path.exists(custom_program_files_dir):
            os.makedirs(custom_program_files_dir)
        program_name = os.path.splitext(os.path.basename(sys.executable if getattr(sys, 'frozen', False) else __file__))[0]
        self.data_dir = os.path.join(custom_program_files_dir, program_name)
        os.makedirs(self.data_dir, exist_ok=True)  # Ensure the directory exists
        self.settings_path = os.path.join(self.data_dir, "settings.json")
        self.config_path = os.path.join(self.data_dir, "config.json")

        # Initialize settings variables
        self.theme_var = tk.StringVar(value="Light")
        self.verbosity = tk.StringVar(value="Status Change")
        self.auto_start_var = tk.BooleanVar(value=False)
        self.auto_sync_var = tk.BooleanVar(value=False)

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s: %(message)s",
            handlers=[
                logging.FileHandler(os.path.join(self.data_dir, "sync_log.txt")),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(__name__)

        # Initialize verbosity setting
        self.verbosity = tk.StringVar(value="Status Change")  # Initialize verbosity

        # Initialize variables
        self.groups = []  # List to store sync groups
        self.is_syncing = False

        # Build GUI
        self.setup_gui()

        # Load existing configuration
        self.load_config()
        # Apply the theme immediately after loading the configuration
        self.apply_theme(self.theme_var.get())

        if self.auto_start_var.get():
            self.log_message("Auto-Start enabled. Auto-Sync will start automatically.", color=Fore.GREEN)
            self.auto_sync_var.set(True)
            self.toggle_auto_sync()

    def setup_gui(self):
        # Main frame layout
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)  # Main content area (row 1)

        # Banner frame at the top
        banner_frame = ttk.Frame(self.root, height=20, relief="raised", padding="5")
        banner_frame.grid(row=0, column=0, sticky="EW")
        self.root.grid_rowconfigure(0, weight=0)  # Fixed height for the banner

        # Add elements to the banner
        # Settings button
        gear_icon_path = os.path.join(self.data_dir, "gear_icon.png")
        if os.path.exists(gear_icon_path):
            image = Image.open(gear_icon_path).convert("RGBA")
            gear_icon = ImageTk.PhotoImage(image.resize((16, 16)))  # Resize to fit the banner
        else:
            messagebox.showerror("Error", f"Gear icon not found: {gear_icon_path}")
            return
        
        # Add buttons to the banner
        add_task_button = ttk.Button(banner_frame, text="Add Task", command=self.open_add_task_window)
        add_task_button.grid(row=0, column=1, sticky="W", padx=5)

        self.remove_task_button = ttk.Button(banner_frame, text="Remove Task", command=self.remove_group, state=tk.DISABLED)
        self.remove_task_button.grid(row=0, column=2, sticky="W", padx=5)

        self.edit_task_button = ttk.Button(banner_frame, text="Edit Task", command=self.open_edit_task_window, state=tk.DISABLED)
        self.edit_task_button.grid(row=0, column=3, sticky="W", padx=5)

        settings_button = ttk.Button(banner_frame, image=gear_icon, command=self.open_settings_window)
        settings_button.image = gear_icon  # Keep reference
        settings_button.grid(row=0, column=0, sticky="W", padx=5)

        self.manual_sync_button = ttk.Button(banner_frame, text="Manual Sync", command=self.manual_sync)
        self.manual_sync_button.grid(row=0, column=5, sticky="W", padx=5)  # Change column to 5

        # Auto Sync checkbox
        self.auto_sync_var = tk.BooleanVar(value=False)
        self.auto_sync_check = ttk.Checkbutton(
            banner_frame, text="Enable Auto-Sync", variable=self.auto_sync_var, command=self.toggle_auto_sync
        )
        self.auto_sync_check.grid(row=0, column=4, sticky="W", padx=5)

        # Treeview frame for the main content
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=1, column=0, sticky="NSEW")
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # Treeview for tasks
        columns = (
            "Task (x/y)", "Master Directory", "Slave Directory", "Status",
            "File Being Processed", "Progress", "Speed", "Auto Interval"
        )
        self.group_tree = ttk.Treeview(main_frame, columns=columns, show="headings")

        # Configure column widths
        self.group_tree.column("Task (x/y)", width=60, anchor="center")
        self.group_tree.column("Master Directory", width=150, anchor="center")
        self.group_tree.column("Slave Directory", width=150, anchor="center")
        self.group_tree.column("Status", width=60, anchor="center")
        self.group_tree.column("File Being Processed", width=200, anchor="center")
        self.group_tree.column("Progress", width=150, anchor="center")
        self.group_tree.column("Speed", width=60, anchor="center")
        self.group_tree.column("Auto Interval", width=100, anchor="center")

        for col in columns:
            self.group_tree.heading(col, text=col)

        self.group_tree.grid(row=0, column=0, sticky="NSEW")

        # Add scrollbars to the treeview
        tree_scroll_y = ttk.Scrollbar(main_frame, orient="vertical", command=self.group_tree.yview)
        self.group_tree.configure(yscroll=tree_scroll_y.set)
        tree_scroll_y.grid(row=0, column=1, sticky="NS")

        tree_scroll_x = ttk.Scrollbar(main_frame, orient="horizontal", command=self.group_tree.xview)
        self.group_tree.configure(xscroll=tree_scroll_x.set)
        tree_scroll_x.grid(row=1, column=0, sticky="EW")

        self.group_tree.bind("<<TreeviewSelect>>", self.update_task_buttons)

        # Log section
        log_frame = ttk.LabelFrame(self.root, text="Sync Log", padding="10")
        log_frame.grid(row=2, column=0, columnspan=2, sticky="NSEW")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, height=10, state=tk.DISABLED, wrap="word")
        self.log_text.grid(row=0, column=0, sticky="NSEW")

        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.grid(row=0, column=1, sticky="NS")
    def open_settings_window(self):
        """Open a floating settings window."""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("400x300")
        settings_window.transient(self.root)  # Make it a child window
        settings_window.grab_set()  # Ensure the settings window is modal
        settings_window.resizable(False, False)

        # Center the settings window on the main window
        x_offset = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (400 // 2)
        y_offset = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (300 // 2)
        settings_window.geometry(f"+{x_offset}+{y_offset}")

        # Add a theme dropdown
        ttk.Label(settings_window, text="Theme:").grid(row=0, column=0, pady=10, sticky="w", padx=20)
        theme_dropdown = ttk.Combobox(settings_window, textvariable=self.theme_var, values=["Light", "Dark", "Hacker", "Gamer", "Modern"], state="readonly")
        theme_dropdown.grid(row=0, column=1, pady=10, sticky="w")

        # Add verbosity dropdown
        ttk.Label(settings_window, text="Verbosity Level:").grid(row=1, column=0, pady=10, sticky="w", padx=20)
        verbosity_dropdown = ttk.Combobox(settings_window, textvariable=self.verbosity, values=["Status Change", "Hyper-Log", "Clean"], state="readonly")
        verbosity_dropdown.grid(row=1, column=1, pady=10, sticky="w")

        # Auto-start checkbox
        ttk.Checkbutton(settings_window, text="Auto-start if Auto-Sync is enabled", variable=self.auto_start_var).grid(row=2, column=0, columnspan=2, pady=10, sticky="w", padx=20)

        # Auto-Sync checkbox
        ttk.Checkbutton(settings_window, text="Enable Auto-Sync by default", variable=self.auto_sync_var).grid(row=3, column=0, columnspan=2, pady=10, sticky="w", padx=20)

        # Bind the `ESC` key to close the window
        settings_window.bind("<Escape>", lambda e: settings_window.destroy())

        # Save settings and close on window close
        settings_window.protocol("WM_DELETE_WINDOW", lambda: self.save_and_close_settings(settings_window))
    def show_tooltip(self, widget, text):
        """Show a tooltip for a widget."""
        self.tooltip = tk.Toplevel(self.root)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{widget.winfo_rootx()}+{widget.winfo_rooty() - 20}")
        label = ttk.Label(self.tooltip, text=text, background="yellow", relief="solid", borderwidth=1, padding=5)
        label.pack()
    def hide_tooltip(self):
        """Hide the tooltip."""
        if hasattr(self, "tooltip"):
            self.tooltip.destroy()
            del self.tooltip

    def apply_theme(self, theme):
        """Apply the selected theme dynamically."""
        style = ttk.Style()

        if theme.lower() == "dark":
            # Configure frame and label styles
            style.configure("TFrame", background="#2b2b2b")
            style.configure("TLabel", background="#2b2b2b", foreground="white")
            style.configure("TButton", background="#3c3f41", foreground="white")
            style.configure("TCheckbutton", background="#2b2b2b", foreground="white")
            style.configure("TCombobox", background="#3c3f41", foreground="white", fieldbackground="#2b2b2b")
            
            # Configure Treeview
            style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0)
            style.configure("Treeview.Heading", background="#3c3f41", foreground="white", font=("Arial", 10, "bold"))
            style.map("Treeview", background=[("selected", "#1f1f1f")], foreground=[("selected", "white")])
            
            # Configure LabelFrame (Log Section)
            style.configure("TLabelFrame", background="#2b2b2b", foreground="white")

            # Configure Scrollbars
            style.configure("Vertical.TScrollbar", background="#3c3f41", troughcolor="#2b2b2b", arrowcolor="white")
            style.configure("Horizontal.TScrollbar", background="#3c3f41", troughcolor="#2b2b2b", arrowcolor="white")

            # Update root window and frames
            self.root.configure(background="#2b2b2b")

        elif theme.lower() == "light":
            # Configure light theme styles
            style.configure("TFrame", background="#f0f0f0")
            style.configure("TLabel", background="#f0f0f0", foreground="black")
            style.configure("TButton", background="#e0e0e0", foreground="black")
            style.configure("TCheckbutton", background="#f0f0f0", foreground="black")
            style.configure("TCombobox", background="white", foreground="black", fieldbackground="white")
            style.configure("Treeview", background="white", foreground="black", fieldbackground="white")
            style.configure("Treeview.Heading", background="white", foreground="black", font=("Arial", 10, "bold"))
            style.configure("TLabelFrame", background="#f0f0f0", foreground="black")
            style.configure("TScrollbar", background="#f0f0f0", troughcolor="#e0e0e0")

        elif theme.lower() == "hacker":  # Black and lime green
            style.configure("TFrame", background="black")
            style.configure("TLabel", background="black", foreground="lime")
            style.configure("TButton", background="#1a1a1a", foreground="lime")
            style.configure("TCheckbutton", background="black", foreground="lime")
            style.configure("TCombobox", background="#1a1a1a", foreground="lime", fieldbackground="black")
            style.configure("Treeview", background="#1a1a1a", foreground="lime", fieldbackground="black")
            style.configure("Treeview.Heading", background="black", foreground="lime", font=("Arial", 10, "bold"))
            style.configure("TLabelFrame", background="black", foreground="lime")
            style.configure("TScrollbar", background="black", troughcolor="#1a1a1a")

        elif theme.lower() == "gamer":  # Black and red
            style.configure("TFrame", background="black")
            style.configure("TLabel", background="black", foreground="red")
            style.configure("TButton", background="#1a1a1a", foreground="red")
            style.configure("TCheckbutton", background="black", foreground="red")
            style.configure("TCombobox", background="#1a1a1a", foreground="red", fieldbackground="black")
            style.configure("Treeview", background="#1a1a1a", foreground="red", fieldbackground="black")
            style.configure("Treeview.Heading", background="black", foreground="red", font=("Arial", 10, "bold"))
            style.configure("TLabelFrame", background="black", foreground="red")
            style.configure("TScrollbar", background="black", troughcolor="#1a1a1a")

        elif theme.lower() == "modern":  # Dark blue and white
            style.configure("TFrame", background="#1e1f29")
            style.configure("TLabel", background="#1e1f29", foreground="white")
            style.configure("TButton", background="#3b3d50", foreground="white")
            style.configure("TCheckbutton", background="#1e1f29", foreground="white")
            style.configure("TCombobox", background="#3b3d50", foreground="white", fieldbackground="#1e1f29")
            style.configure("Treeview", background="#3b3d50", foreground="white", fieldbackground="#1e1f29")
            style.configure("Treeview.Heading", background="#1e1f29", foreground="white", font=("Arial", 10, "bold"))
            style.configure("TLabelFrame", background="#1e1f29", foreground="white")
            style.configure("TScrollbar", background="#1e1f29", troughcolor="#3b3d50")

        else:
            self.log_message(f"Unknown theme: {theme}. Using default theme.", color=Fore.RED)

        # Refresh the GUI to apply changes
        self.root.update_idletasks()
    def auto_sync_loop(self):
        """Auto-Sync Loop: Perform sync operations periodically based on group intervals."""
        while self.is_syncing:
            for group in self.groups:
                interval = self.parse_interval(group["interval"])
                last_sync_time = group.get("last_sync_time", 0)

                # Check if the interval has passed
                if time.time() - last_sync_time >= interval:
                    group["last_sync_time"] = time.time()  # Update last sync time
                    threading.Thread(target=self.sync_group, args=(group,), daemon=True).start()

            # Sleep for a short duration before the next iteration
            time.sleep(1)
    def add_group(self):
        def save_group():
            master_dir = master_entry.get()
            slave_dir = slave_entry.get()
            interval = interval_var.get()

            if not master_dir or not slave_dir:
                messagebox.showerror("Error", "Both directories must be selected.")
                return

            group = {
                "master": master_dir,
                "slave": slave_dir,
                "status": "Idle",
                "file_being_processed": "N/A",
                "progress": "0%",
                "speed": "N/A",
                "task": "0/0",
                "interval": interval,
                "files_to_process": 0,
                "files_processed": 0
            }
            self.groups.append(group)
            self.log_message(f"Added new group: Master: {master_dir}, Slave: {slave_dir}, Interval: {interval}", color=Fore.GREEN)
            self.update_tree()
            self.save_config()  # Automatically save configuration after adding a group
            group_window.destroy()

        group_window = tk.Toplevel(self.root)
        group_window.title("Add Sync Group")

        ttk.Label(group_window, text="Master Directory:").grid(row=0, column=0, sticky="W")
        master_entry = ttk.Entry(group_window, width=50)
        master_entry.grid(row=0, column=1)

        master_browse = ttk.Button(group_window, text="Browse", command=lambda: master_entry.insert(0, filedialog.askdirectory()))
        master_browse.grid(row=0, column=2)

        ttk.Label(group_window, text="Slave Directory:").grid(row=1, column=0, sticky="W")
        slave_entry = ttk.Entry(group_window, width=50)
        slave_entry.grid(row=1, column=1)

        slave_browse = ttk.Button(group_window, text="Browse", command=lambda: slave_entry.insert(0, filedialog.askdirectory()))
        slave_browse.grid(row=1, column=2)

        ttk.Label(group_window, text="Sync Interval:").grid(row=2, column=0, sticky="W")
        interval_var = tk.StringVar(value="5m")
        interval_menu = ttk.Combobox(group_window, textvariable=interval_var, values=["5m", "15m", "1h", "4h", "1d", "1w"], state="readonly")
        interval_menu.grid(row=2, column=1)

        save_button = ttk.Button(group_window, text="Save", command=save_group)
        save_button.grid(row=3, column=0, columnspan=3)
    def create_progress_bar(self, percent):
        """Create a text-based progress bar"""
        bar_length = 20
        filled_length = int(bar_length * percent / 100)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        return f"{percent:6.2f}% [{bar}]"
    def copy_file_with_progress(self, src, dest, group):
        """Copy a file and update the progress dynamically."""
        total_size = os.path.getsize(src)
        copied_size = 0
        buffer_size = 1024 * 1024  # 1 MB

        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(src, "rb") as src_file, open(dest, "wb") as dest_file:
            while chunk := src_file.read(buffer_size):
                dest_file.write(chunk)
                copied_size += len(chunk)

                # Update progress
                progress = (copied_size / total_size) * 100
                group["progress"] = f"{progress:.2f}%"
                self.update_tree_item(group)
    def load_config(self):
        """Load both settings and groups from config.json."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    config_data = json.load(f)
                
                # Load settings
                settings = config_data.get("settings", {})
                self.theme_var.set(settings.get("theme", "Light"))
                self.verbosity.set(settings.get("verbosity", "Status Change"))
                self.auto_start_var.set(settings.get("auto_start", False))
                self.auto_sync_var.set(settings.get("auto_sync", False))
                
                # Apply the theme immediately
                self.apply_theme(self.theme_var.get())
                
                # Load groups
                self.groups = config_data.get("groups", [])
                self.update_tree()

                self.log_message("Configuration loaded successfully.", color=Fore.GREEN)
            except Exception as e:
                self.log_message(f"Error loading config.json: {e}", color=Fore.RED)
        else:
            self.log_message("No config.json file found. Starting with default settings.", color=Fore.YELLOW)
    def log_message(self, message, color=Fore.WHITE, log_type="general"):
        """
        Log messages to both the console and the sync log based on verbosity.
        :param message: Message to log.
        :param color: Text color for the GUI log.
        :param log_type: Log category: "status", "operation", or "metrics".
        """
        verbosity = self.verbosity.get()

        # Handle verbosity levels
        if verbosity == "Clean":
            return  # No logs
        elif verbosity == "Status Change" and log_type not in ["status"]:
            return  # Skip non-status messages in Status Change mode

        # Log to the GUI
        colored_message = color + message + Style.RESET_ALL
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)

        # Log to console and file
        if color == Fore.RED:
            self.logger.error(message)
        elif color == Fore.GREEN:
            self.logger.info(message)
        elif color == Fore.YELLOW:
            self.logger.warning(message)
        else:
            self.logger.info(message)
    def manual_sync(self):
        if not self.groups:
            messagebox.showwarning("No Groups", "No sync groups defined.")
            return

        self.log_message("Starting manual sync for all groups...", color=Fore.CYAN)
        for group in self.groups:
            threading.Thread(target=self.sync_group, args=(group,), daemon=True).start()
    def open_add_task_window(self):
        """Open the embedded Add Task window."""
        add_task_window = tk.Toplevel(self.root)
        add_task_window.title("Add Task")
        add_task_window.geometry("500x300")
        add_task_window.transient(self.root)
        add_task_window.grab_set()

        ttk.Label(add_task_window, text="Master Directory:").grid(row=0, column=0, sticky="W", padx=10, pady=10)
        master_entry = ttk.Entry(add_task_window, width=40)
        master_entry.grid(row=0, column=1, padx=10, pady=10)
        
        ttk.Button(add_task_window, text="Browse", command=lambda: master_entry.insert(0, filedialog.askdirectory())).grid(row=0, column=2)

        ttk.Label(add_task_window, text="Slave Directory:").grid(row=1, column=0, sticky="W", padx=10, pady=10)
        slave_entry = ttk.Entry(add_task_window, width=40)
        slave_entry.grid(row=1, column=1, padx=10, pady=10)

        ttk.Button(add_task_window, text="Browse", command=lambda: slave_entry.insert(0, filedialog.askdirectory())).grid(row=1, column=2)

        ttk.Label(add_task_window, text="Sync Interval:").grid(row=2, column=0, sticky="W", padx=10, pady=10)
        interval_var = tk.StringVar(value="1m")
        interval_menu = ttk.Combobox(add_task_window, textvariable=interval_var, values=["1m", "5m", "15m", "1h", "4h", "1d", "1w"], state="readonly")
        interval_menu.grid(row=2, column=1, padx=10, pady=10)

        def save_task():
            master_dir = master_entry.get()
            slave_dir = slave_entry.get()
            interval = interval_var.get()

            if not master_dir or not slave_dir:
                messagebox.showerror("Error", "Both directories must be specified.")
                return

            group = {
                "master": master_dir,
                "slave": slave_dir,
                "status": "Idle",
                "file_being_processed": "N/A",
                "progress": "0.0%",
                "speed": "N/A",
                "task": "0/0",
                "interval": interval,
            }
            self.groups.append(group)
            self.update_tree()
            self.save_config()
            add_task_window.destroy()

        save_button = ttk.Button(add_task_window, text="Save Task", command=save_task)
        save_button.grid(row=3, column=0, columnspan=3, pady=20)
    def open_edit_task_window(self):
        """Open the embedded Edit Task window."""
        selected_item = self.group_tree.selection()
        if not selected_item:
            return

        # Get selected group
        index = int(selected_item[0])  # Get the treeview ID
        group = self.groups[index]

        edit_task_window = tk.Toplevel(self.root)
        edit_task_window.title("Edit Task")
        edit_task_window.geometry("500x300")
        edit_task_window.transient(self.root)
        edit_task_window.grab_set()

        ttk.Label(edit_task_window, text="Master Directory:").grid(row=0, column=0, sticky="W", padx=10, pady=10)
        master_entry = ttk.Entry(edit_task_window, width=40)
        master_entry.insert(0, group["master"])
        master_entry.grid(row=0, column=1, padx=10, pady=10)

        ttk.Button(edit_task_window, text="Browse", command=lambda: master_entry.delete(0, tk.END) or master_entry.insert(0, filedialog.askdirectory())).grid(row=0, column=2)

        ttk.Label(edit_task_window, text="Slave Directory:").grid(row=1, column=0, sticky="W", padx=10, pady=10)
        slave_entry = ttk.Entry(edit_task_window, width=40)
        slave_entry.insert(0, group["slave"])
        slave_entry.grid(row=1, column=1, padx=10, pady=10)

        ttk.Button(edit_task_window, text="Browse", command=lambda: slave_entry.delete(0, tk.END) or slave_entry.insert(0, filedialog.askdirectory())).grid(row=1, column=2)

        ttk.Label(edit_task_window, text="Sync Interval:").grid(row=2, column=0, sticky="W", padx=10, pady=10)
        interval_var = tk.StringVar(value=group["interval"])
        interval_menu = ttk.Combobox(edit_task_window, textvariable=interval_var, values=["1m", "5m", "15m", "1h", "4h", "1d", "1w"], state="readonly")
        interval_menu.grid(row=2, column=1, padx=10, pady=10)

        def save_changes():
            group["master"] = master_entry.get()
            group["slave"] = slave_entry.get()
            group["interval"] = interval_var.get()
            self.update_tree()
            self.save_config()
            edit_task_window.destroy()

        save_button = ttk.Button(edit_task_window, text="Save Changes", command=save_changes)
        save_button.grid(row=3, column=0, columnspan=3, pady=20)
    def parse_interval(self, interval):
        """Parse interval string (e.g., '5m', '1h') into seconds."""
        time_mapping = {
            "m": 60,
            "h": 3600,
            "d": 86400,
            "w": 604800
        }
        try:
            value = int(interval[:-1])
            unit = interval[-1]
            return value * time_mapping.get(unit, 60)  # Default to minutes if unit is unknown
        except (ValueError, KeyError):
            self.log_message(f"Invalid interval format: {interval}", color=Fore.RED)
            return 300  # Default to 5 minutes
    def remove_group(self):
        selected_item = self.group_tree.selection()
        if not selected_item:
            return

        index = int(selected_item[0]) - 1
        removed_group = self.groups.pop(index)
        self.log_message(f"Removed group: Master: {removed_group['master']}, Slave: {removed_group['slave']}", color=Fore.YELLOW)
        self.update_tree()
        self.save_config()  # Save configuration after removing a group
    def save_config(self):
        """Save both settings and groups to config.json."""
        config_data = {
            "settings": {
                "theme": self.theme_var.get(),
                "verbosity": self.verbosity.get(),
                "auto_start": self.auto_start_var.get(),
                "auto_sync": self.auto_sync_var.get(),
            },
            "groups": self.groups,
        }
        try:
            with open(self.config_path, "w") as f:
                json.dump(config_data, f, indent=4)
            self.log_message("Configuration saved successfully.", color=Fore.CYAN)
            # Load existing configuration
            self.load_config()
            # Apply the theme immediately after loading the configuration
            self.apply_theme(self.theme_var.get())

        except Exception as e:
            self.log_message(f"Error saving config.json: {e}", color=Fore.RED)
    def save_and_close_settings(self, settings_window):
        """Save settings and close the settings window."""
        self.save_config()  # Save settings and groups to config.json
        settings_window.destroy()  # Close the window
    def sync_group(self, group):
        """Perform the sync operation for a specific group."""
        self.log_message(f"[{datetime.now()}]Starting sync for group: Master {group['master']} -> Slave {group['slave']}", color=Fore.GREEN, log_type="status")
        group["status"] = "Checking Files"
        self.update_tree_item(group)

        master_dir = group["master"]
        slave_dir = group["slave"]
        tasks = []  # To hold all sync tasks (copy, update, delete)
        total_files = 0

        # Step 1: Check for differences
        for root, _, files in os.walk(master_dir):
            for file in files:
                master_file = os.path.join(root, file)
                relative_path = os.path.relpath(master_file, master_dir)
                slave_file = os.path.join(slave_dir, relative_path)

                total_files += 1
                self.log_message(f"Checking: {relative_path}", color=Fore.YELLOW, log_type="operation")

                # If the file is missing in the slave directory
                if not os.path.exists(slave_file):
                    tasks.append(("copy", master_file, slave_file))
                    self.log_message(f"File missing, queued for copy: {relative_path}", color=Fore.YELLOW, log_type="metrics")
                else:
                    # If the file exists but is outdated
                    if os.path.getsize(master_file) > os.path.getsize(slave_file):
                        tasks.append(("update", master_file, slave_file))
                        self.log_message(f"Outdated file, queued for update: {relative_path}", color=Fore.YELLOW, log_type="metrics")

        # Check for extra files in the slave directory
        for root, _, files in os.walk(slave_dir):
            for file in files:
                slave_file = os.path.join(root, file)
                relative_path = os.path.relpath(slave_file, slave_dir)
                master_file = os.path.join(master_dir, relative_path)

                if not os.path.exists(master_file):
                    tasks.append(("delete", slave_file))
                    self.log_message(f"Extra file, queued for delete: {relative_path}", color=Fore.YELLOW, log_type="metrics")

        # Update group status
        group["task"] = f"0/{total_files}"
        group["status"] = "Syncing"
        group["progress"] = "0%"
        self.update_tree_item(group)

        # Step 2: Execute tasks
        total_tasks = len(tasks)
        for index, (operation, src, dest) in enumerate(tasks, start=1):
            group["task"] = f"{index}/{total_tasks}"
            group["file_being_processed"] = os.path.basename(src if operation != "delete" else dest)

            # Reset progress for each operation
            group["progress"] = "0%"
            self.update_tree_item(group)

            start_time = time.time()
            if operation == "copy":
                self.copy_file_with_progress(src, dest, group)
                self.log_message(f"Copied: {src} -> {dest}", color=Fore.GREEN, log_type="operation")
            elif operation == "update":
                self.copy_file_with_progress(src, dest, group)
                self.log_message(f"Updated: {src} -> {dest}", color=Fore.GREEN, log_type="operation")
            elif operation == "delete":
                os.remove(dest)
                self.log_message(f"Deleted: {dest}", color=Fore.YELLOW, log_type="operation")

            elapsed_time = time.time() - start_time
            speed = os.path.getsize(src if operation != "delete" else dest) / (1024 * 1024 * elapsed_time) if elapsed_time > 0 else 0
            group["speed"] = f"{speed:.2f} MB/s"
            self.log_message(f"Speed: {speed:.2f} MB/s", color=Fore.CYAN, log_type="metrics")
            self.update_tree_item(group)

        group["status"] = "Completed"
        group["file_being_processed"] = "N/A"
        group["progress"] = "100%"
        self.update_tree_item(group)
        self.log_message(f"[{datetime.now()}]Sync completed for group: Master {group['master']} -> Slave {group['slave']}", color=Fore.GREEN, log_type="status")
    def toggle_auto_sync(self):
        """Toggle Auto-Sync functionality."""
        if self.auto_sync_var.get():
            self.is_syncing = True
            self.log_message("Auto-Sync enabled.", color=Fore.CYAN)
            threading.Thread(target=self.auto_sync_loop, daemon=True).start()
        else:
            self.is_syncing = False
            self.log_message("Auto-Sync disabled.", color=Fore.CYAN)
    def update_tree_item(self, group):
        """Update the TreeView item for a specific sync group."""
        try:
            group_id = self.groups.index(group)  # Get the index of the group in the list
            new_values = [
                group["task"],  # Task (x/y)
                group["master"],  # Master Directory
                group["slave"],  # Slave Directory
                group["status"],  # Status
                group["file_being_processed"],  # File Being Processed
                group["progress"],  # Progress
                group["speed"],  # Speed
                group["interval"],  # Auto Interval
            ]
            self.group_tree.item(str(group_id), values=new_values)
        except ValueError:
            self.log_message("Group not found in the list. Skipping update.", color=Fore.RED)
    def update_tree(self):
        self.group_tree.delete(*self.group_tree.get_children())  # Clear existing items
        for i, group in enumerate(self.groups):
            self.group_tree.insert("", "end", iid=str(i), values=(
                group["task"],
                group["master"],
                group["slave"],
                group["status"],
                group["file_being_processed"],
                group["progress"],
                group["speed"],
                group["interval"],
            ))
    def update_task_buttons(self, event=None):
        """Enable or disable buttons based on task selection."""
        selected_item = self.group_tree.selection()
        if selected_item:  # Check if any item is selected
            self.remove_task_button.config(state=tk.NORMAL)
            self.edit_task_button.config(state=tk.NORMAL)
        else:
            self.remove_task_button.config(state=tk.DISABLED)
            self.edit_task_button.config(state=tk.DISABLED)
    
if __name__ == "__main__":
    root = tk.Tk()
    app = DirectorySyncApp(root)
    root.mainloop()
