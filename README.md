# PNG Sequence Renamer

🖼️ A cross-platform desktop tool for batch renaming PNG files with preview and undo functionality.

## Features
- ✅ Batch rename PNG files with live preview
- ✅ Colorful interface (red = old names, green = new names)
- ✅ Auto-update system built-in
- ✅ Undo functionality with CSV logging
- ✅ Natural sorting (handles numbers correctly)
- ✅ Cross-platform support (Windows/Mac/Linux)

## Download
**[Download Latest Release](https://github.com/gouravbhagat20/png-sequence-renamer/releases/latest)**

No Python installation required! Just download the `.exe` file and run it.

# 1. Install PyInstaller
pip install pyinstaller

# 2. Verify it's installed
pip show pyinstaller

# 3. Build your executable
python -m PyInstaller --onefile --windowed --name="PNG-Sequence-Renamer-v1.0.0" png_sequence_renamer_gui_v1.0.0.py

## Screenshots
![PNG Renamer Interface](screenshot.png)

## How to Use
1. Browse and select a folder containing PNG files
2. Enter your desired basename (e.g., "frame")
3. Configure options (start index, padding, prefix/suffix)
4. Click "Preview" to see planned renames
5. Click "Rename" to execute safely
6. Use "Undo" if needed

## Developer
Created by [Gourav Bhagat](https://github.com/gouravbhagat20)
