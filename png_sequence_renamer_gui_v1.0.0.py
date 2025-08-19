#!/usr/bin/env python3
"""
PNG Sequence Renamer GUI with Auto-Update System
Enhanced version with built-in update checking and deployment
"""

import os
import re
import csv
import shutil
import tempfile
import json
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import zipfile

# Version information
__version__ = "1.0.0"
__author__ = "Your Name"
UPDATE_CHECK_URL = "https://api.github.com/repos/gouravbhagat20/png-sequence-renamer/releases/latest"
DOWNLOAD_URL = "https://github.com/gouravbhagat20/png-sequence-renamer/releases/latest/download/"


def natural_sort_key(text):
    """Convert a string into a list of string and number chunks for natural sorting."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', str(text))]


def get_png_files(folder_path, sort_mode):
    """Get all PNG files from folder and sort them according to sort_mode."""
    try:
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            return []
        
        # Find all PNG files (case-insensitive)
        png_files = []
        for file_path in folder.iterdir():
            if file_path.is_file() and file_path.suffix.lower() == '.png':
                png_files.append(file_path)
        
        # Sort based on mode
        if sort_mode == "Name":
            png_files.sort(key=lambda x: natural_sort_key(x.name))
        elif sort_mode == "Modified":
            png_files.sort(key=lambda x: x.stat().st_mtime)
        elif sort_mode == "Created":
            png_files.sort(key=lambda x: x.stat().st_ctime)
        
        return png_files
    except Exception:
        return []


def plan_renames(png_files, basename, start_index, zero_padding, prefix, suffix):
    """Plan the rename operations and return a list of (old_path, new_name) tuples."""
    if not basename.strip():
        raise ValueError("Basename is required")
    
    if not png_files:
        return []
    
    # Auto-detect padding if not specified
    if zero_padding == 0:
        total_files = len(png_files)
        max_index = start_index + total_files - 1
        zero_padding = len(str(max_index))
    
    renames = []
    for i, old_path in enumerate(png_files):
        index = start_index + i
        index_str = str(index).zfill(zero_padding)
        new_name = f"{prefix}{basename}_{index_str}{suffix}.png"
        renames.append((old_path, new_name))
    
    return renames


def detect_collisions(renames, folder_path):
    """Detect naming collisions and return list of collision messages."""
    folder = Path(folder_path)
    collisions = []
    new_names = set()
    
    for old_path, new_name in renames:
        new_path = folder / new_name
        
        # Check if new name already used in this rename batch
        if new_name in new_names:
            collisions.append(f"Duplicate target name: {new_name}")
        new_names.add(new_name)
        
        # Check if target file exists and is not the same file being renamed
        if new_path.exists() and new_path != old_path:
            collisions.append(f"Would overwrite existing file: {new_name}")
    
    return collisions


def two_phase_rename(renames, folder_path):
    """Execute renames using two-phase method to avoid clobbering."""
    folder = Path(folder_path)
    temp_names = []
    
    try:
        # Phase 1: Rename to temporary names
        for old_path, new_name in renames:
            if old_path.name != new_name:  # Skip if already correctly named
                temp_name = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{old_path.name}"
                temp_path = folder / temp_name
                old_path.rename(temp_path)
                temp_names.append((temp_path, new_name))
        
        # Phase 2: Rename from temporary to final names
        final_renames = []
        for temp_path, new_name in temp_names:
            new_path = folder / new_name
            temp_path.rename(new_path)
            # Store original and final paths for logging
            original_name = temp_path.name.split('_', 3)[-1] if '_' in temp_path.name else temp_path.name
            original_path = folder / original_name
            final_renames.append((original_path, new_path))
        
        return final_renames
    
    except Exception as e:
        # Attempt to rollback phase 1 if phase 2 fails
        for temp_path, _ in temp_names:
            if temp_path.exists():
                try:
                    original_name = temp_path.name.split('_', 3)[-1] if '_' in temp_path.name else temp_path.name
                    original_path = folder / original_name
                    temp_path.rename(original_path)
                except:
                    pass
        raise e


def write_log(renames, log_file_path):
    """Write rename operations to CSV log file."""
    try:
        with open(log_file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['old_path', 'new_path', 'timestamp'])
            timestamp = datetime.now().isoformat()
            for old_path, new_path in renames:
                writer.writerow([str(old_path), str(new_path), timestamp])
    except Exception as e:
        raise Exception(f"Failed to write log: {e}")


def undo_from_log(log_file_path):
    """Undo renames by reading from CSV log file."""
    if not os.path.exists(log_file_path):
        raise FileNotFoundError("Log file not found")
    
    try:
        with open(log_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            undone = []
            for row in reader:
                new_path = Path(row['new_path'])
                old_path = Path(row['old_path'])
                
                if new_path.exists():
                    new_path.rename(old_path)
                    undone.append((new_path, old_path))
        
        # Remove the log file after successful undo
        os.remove(log_file_path)
        return undone
    
    except Exception as e:
        raise Exception(f"Failed to undo renames: {e}")


class UpdateChecker:
    """Handle update checking and downloading."""
    
    @staticmethod
    def check_for_updates():
        """Check if a newer version is available."""
        try:
            with urllib.request.urlopen(UPDATE_CHECK_URL, timeout=5) as response:
                data = json.loads(response.read().decode())
                latest_version = data['tag_name'].lstrip('v')
                download_url = data['assets'][0]['browser_download_url'] if data['assets'] else None
                
                return {
                    'available': latest_version != __version__,
                    'version': latest_version,
                    'download_url': download_url,
                    'release_notes': data.get('body', 'No release notes available.')
                }
        except Exception as e:
            return {'available': False, 'error': str(e)}
    
    @staticmethod
    def download_update(download_url, callback=None):
        """Download the update file."""
        try:
            filename = download_url.split('/')[-1]
            temp_file = os.path.join(tempfile.gettempdir(), filename)
            
            def progress_hook(block_num, block_size, total_size):
                if callback and total_size > 0:
                    percent = min(100, (block_num * block_size * 100) // total_size)
                    callback(percent)
            
            urllib.request.urlretrieve(download_url, temp_file, progress_hook)
            return temp_file
        except Exception as e:
            raise Exception(f"Download failed: {e}")


class PNGRenamerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"PNG Sequence Renamer v{__version__}")
        self.root.geometry("850x650")
        
        # Variables
        self.folder_path = tk.StringVar()
        self.basename = tk.StringVar(value="frame")
        self.start_index = tk.IntVar(value=1)
        self.zero_padding = tk.IntVar(value=0)
        self.prefix = tk.StringVar()
        self.suffix = tk.StringVar()
        self.sort_mode = tk.StringVar(value="Name")
        
        self.current_renames = []
        self.log_file_path = ""
        
        self.setup_ui()
        
        # Check for updates on startup (optional)
        self.check_updates_on_startup()
    
    def setup_ui(self):
        """Set up the user interface."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(7, weight=1)
        
        # Title with version
        title_label = ttk.Label(main_frame, text=f"🖼️ PNG Sequence Renamer v{__version__}", 
                               font=('Arial', 12, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        
        # Folder selection
        ttk.Label(main_frame, text="Folder:").grid(row=1, column=0, sticky=tk.W, pady=2)
        folder_frame = ttk.Frame(main_frame)
        folder_frame.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=2)
        folder_frame.columnconfigure(0, weight=1)
        
        ttk.Entry(folder_frame, textvariable=self.folder_path, state='readonly').grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(folder_frame, text="Browse", command=self.browse_folder).grid(row=0, column=1)
        
        # Basename (required)
        ttk.Label(main_frame, text="Basename*:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(main_frame, textvariable=self.basename).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2)
        
        # Start index
        ttk.Label(main_frame, text="Start Index:").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(main_frame, textvariable=self.start_index, width=10).grid(row=3, column=1, sticky=tk.W, pady=2)
        
        # Zero padding
        ttk.Label(main_frame, text="Zero Padding:").grid(row=4, column=0, sticky=tk.W, pady=2)
        padding_frame = ttk.Frame(main_frame)
        padding_frame.grid(row=4, column=1, sticky=tk.W, pady=2)
        ttk.Entry(padding_frame, textvariable=self.zero_padding, width=10).grid(row=0, column=0)
        ttk.Label(padding_frame, text="(0 = auto-detect)").grid(row=0, column=1, padx=(5, 0))
        
        # Prefix
        ttk.Label(main_frame, text="Prefix:").grid(row=5, column=0, sticky=tk.W, pady=2)
        ttk.Entry(main_frame, textvariable=self.prefix).grid(row=5, column=1, sticky=(tk.W, tk.E), pady=2)
        
        # Suffix
        ttk.Label(main_frame, text="Suffix:").grid(row=6, column=0, sticky=tk.W, pady=2)
        ttk.Entry(main_frame, textvariable=self.suffix).grid(row=6, column=1, sticky=(tk.W, tk.E), pady=2)
        
        # Sort mode
        ttk.Label(main_frame, text="Sort by:").grid(row=7, column=0, sticky=tk.W, pady=2)
        sort_combo = ttk.Combobox(main_frame, textvariable=self.sort_mode, values=["Name", "Modified", "Created"], state='readonly')
        sort_combo.grid(row=7, column=1, sticky=tk.W, pady=2)
        
        # Preview area
        preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding="5")
        preview_frame.grid(row=8, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        
        # Treeview for preview with colorful styling
        self.preview_tree = ttk.Treeview(preview_frame, columns=('old', 'new'), show='headings', height=10)
        self.preview_tree.heading('old', text='📁 Current Name')
        self.preview_tree.heading('new', text='✨ New Name')
        self.preview_tree.column('old', width=350)
        self.preview_tree.column('new', width=350)
        
        # Configure colorful tags for the treeview
        self.preview_tree.tag_configure('old_file', background='#FFE6E6', foreground='#8B0000')
        self.preview_tree.tag_configure('new_file', background='#E6FFE6', foreground='#006400')
        self.preview_tree.tag_configure('alternate', background='#F0F0F0')
        
        # Scrollbars for treeview
        v_scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.preview_tree.yview)
        h_scrollbar = ttk.Scrollbar(preview_frame, orient=tk.HORIZONTAL, command=self.preview_tree.xview)
        self.preview_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.preview_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=9, column=0, columnspan=3, pady=(10, 0))
        
        ttk.Button(button_frame, text="Preview", command=self.preview_renames).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Rename", command=self.execute_renames).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Undo", command=self.undo_renames).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🔄 Check Updates", command=self.check_for_updates).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Exit", command=self.root.quit).pack(side=tk.RIGHT)
        
        # Enhanced status bar with color
        self.status_var = tk.StringVar(value="🚀 Ready - Select a folder to begin")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, 
                               background='#E8F4FD', foreground='#2C5282')
        status_bar.grid(row=10, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))
    
    def browse_folder(self):
        """Open folder selection dialog."""
        folder = filedialog.askdirectory()
        if folder:
            self.folder_path.set(folder)
            self.status_var.set(f"📂 Selected folder: {os.path.basename(folder)}")
    
    def preview_renames(self):
        """Preview the planned renames."""
        try:
            # Clear previous preview
            for item in self.preview_tree.get_children():
                self.preview_tree.delete(item)
            
            if not self.folder_path.get():
                messagebox.showerror("Error", "Please select a folder first.")
                return
            
            if not self.basename.get().strip():
                messagebox.showerror("Error", "Basename is required.")
                return
            
            # Get PNG files
            png_files = get_png_files(self.folder_path.get(), self.sort_mode.get())
            
            if not png_files:
                self.status_var.set("⚠️ No PNG files found in selected folder.")
                return
            
            # Plan renames
            self.current_renames = plan_renames(
                png_files,
                self.basename.get().strip(),
                self.start_index.get(),
                self.zero_padding.get(),
                self.prefix.get(),
                self.suffix.get()
            )
            
            # Check for collisions
            collisions = detect_collisions(self.current_renames, self.folder_path.get())
            if collisions:
                collision_msg = "Naming collisions detected:\n\n" + "\n".join(collisions[:10])
                if len(collisions) > 10:
                    collision_msg += f"\n... and {len(collisions) - 10} more"
                messagebox.showerror("Collision Error", collision_msg)
                return
            
            # Populate preview with alternating colors
            for i, (old_path, new_name) in enumerate(self.current_renames):
                # Determine row tags for coloring
                tags = []
                if i % 2 == 1:  # Alternate row background
                    tags.append('alternate')
                
                # Insert with color-coded values
                item_id = self.preview_tree.insert('', 'end', values=(old_path.name, new_name), tags=tags)
                
                # Apply cell-specific styling by configuring the item
                self.preview_tree.set(item_id, 'old', f"🔴 {old_path.name}")  # Red circle for old
                self.preview_tree.set(item_id, 'new', f"🟢 {new_name}")       # Green circle for new
            
            self.status_var.set(f"✅ Preview ready: {len(self.current_renames)} files to rename")
        
        except Exception as e:
            messagebox.showerror("Error", f"Preview failed: {e}")
            self.status_var.set("Preview failed")
    
    def execute_renames(self):
        """Execute the planned renames."""
        if not self.current_renames:
            messagebox.showwarning("Warning", "No renames planned. Click Preview first.")
            return
        
        # Confirm with user
        if not messagebox.askyesno("Confirm Rename", 
                                   f"Are you sure you want to rename {len(self.current_renames)} files?"):
            return
        
        try:
            # Execute two-phase rename
            completed_renames = two_phase_rename(self.current_renames, self.folder_path.get())
            
            # Write log file
            self.log_file_path = os.path.join(self.folder_path.get(), "rename_log.csv")
            write_log(completed_renames, self.log_file_path)
            
            # Clear preview
            for item in self.preview_tree.get_children():
                self.preview_tree.delete(item)
            
            self.current_renames = []
            self.status_var.set(f"🎉 Successfully renamed {len(completed_renames)} files")
            
            messagebox.showinfo("Success", f"Renamed {len(completed_renames)} files successfully!\nLog saved to: rename_log.csv")
        
        except Exception as e:
            messagebox.showerror("Error", f"Rename failed: {e}")
            self.status_var.set("Rename failed")
    
    def undo_renames(self):
        """Undo the last rename operation."""
        log_path = os.path.join(self.folder_path.get() if self.folder_path.get() else "", "rename_log.csv")
        
        if not os.path.exists(log_path):
            messagebox.showwarning("Warning", "No undo log found. Cannot undo.")
            return
        
        if not messagebox.askyesno("Confirm Undo", "Are you sure you want to undo the last rename operation?"):
            return
        
        try:
            undone_files = undo_from_log(log_path)
            self.status_var.set(f"Undone {len(undone_files)} renames")
            messagebox.showinfo("Success", f"Successfully undone {len(undone_files)} renames")
        
        except Exception as e:
            messagebox.showerror("Error", f"Undo failed: {e}")
            self.status_var.set("Undo failed")
    
    def check_updates_on_startup(self):
        """Check for updates when the app starts (non-blocking)."""
        def check():
            try:
                update_info = UpdateChecker.check_for_updates()
                if update_info.get('available'):
                    self.root.after(0, lambda: self.show_update_notification(update_info))
            except:
                pass  # Silently fail on startup check
        
        thread = threading.Thread(target=check, daemon=True)
        thread.start()
    
    def check_for_updates(self):
        """Manual update check triggered by button."""
        self.status_var.set("🔍 Checking for updates...")
        
        def check():
            try:
                update_info = UpdateChecker.check_for_updates()
                self.root.after(0, lambda: self.handle_update_result(update_info))
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"❌ Update check failed: {e}"))
        
        thread = threading.Thread(target=check, daemon=True)
        thread.start()
    
    def handle_update_result(self, update_info):
        """Handle the result of update check."""
        if update_info.get('available'):
            self.show_update_notification(update_info)
        elif update_info.get('error'):
            self.status_var.set(f"❌ Update check failed: {update_info['error']}")
        else:
            self.status_var.set("✅ You have the latest version!")
            messagebox.showinfo("Up to Date", "You're already using the latest version!")
    
    def show_update_notification(self, update_info):
        """Show update notification dialog."""
        message = (f"🎉 New version available!\n\n"
                  f"Current version: {__version__}\n"
                  f"Latest version: {update_info['version']}\n\n"
                  f"Release notes:\n{update_info['release_notes'][:200]}...\n\n"
                  f"Would you like to download the update?")
        
        if messagebox.askyesno("Update Available", message):
            self.download_update(update_info['download_url'])
    
    def download_update(self, download_url):
        """Download and install update."""
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Downloading Update")
        progress_window.geometry("400x100")
        progress_window.resizable(False, False)
        
        ttk.Label(progress_window, text="Downloading update...").pack(pady=10)
        progress_bar = ttk.Progressbar(progress_window, mode='determinate')
        progress_bar.pack(fill=tk.X, padx=20, pady=10)
        
        def progress_callback(percent):
            progress_bar['value'] = percent
            progress_window.update()
        
        def download():
            try:
                temp_file = UpdateChecker.download_update(download_url, progress_callback)
                self.root.after(0, lambda: self.install_update(temp_file, progress_window))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Download Failed", f"Failed to download update: {e}"))
                progress_window.destroy()
        
        thread = threading.Thread(target=download, daemon=True)
        thread.start()
    
    def install_update(self, update_file, progress_window):
        """Install the downloaded update."""
        progress_window.destroy()
        
        message = (f"Update downloaded successfully!\n\n"
                  f"The new version has been saved to:\n{update_file}\n\n"
                  f"Please close this application and run the new version.")
        
        messagebox.showinfo("Update Ready", message)
        
        # Optionally, try to open the file location
        try:
            if os.name == 'nt':  # Windows
                os.startfile(os.path.dirname(update_file))
            elif os.name == 'posix':  # macOS/Linux
                os.system(f'open "{os.path.dirname(update_file)}"')
        except:
            pass


def main():
    """Main entry point for the GUI application."""
    root = tk.Tk()
    app = PNGRenamerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
