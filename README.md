<div align="center">
  <img src="assets/compressly-logo.png" alt="Compressly Logo" width="120" />

  # Compressly

  **A modern, privacy-first image compression desktop app for Windows**

  [![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
  [![PySide6](https://img.shields.io/badge/PySide6-6.8.1-41CD52?style=flat-square&logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
  [![Pillow](https://img.shields.io/badge/Pillow-11.0.0-blue?style=flat-square)](https://python-pillow.org/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)
  [![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?style=flat-square&logo=windows&logoColor=white)](https://www.microsoft.com/windows)

  *No Electron. No Node. No telemetry. 100% local.*

</div>

---

## Overview

Compressly is a lightweight, native Windows desktop application for batch image compression and format conversion. Built with **PySide6** and **Pillow**, it gives you full control over your images — all processing happens locally on your machine with zero data sent anywhere.

### Why Compressly?

| Feature | Compressly | Typical web tools |
|---|---|---|
| Privacy | Yes (100% local) | No (Uploads your images) |
| Batch processing | Yes (Multi-threaded) | Limited |
| Offline support | Yes (Always works) | No (Requires internet) |
| No install bloat | Yes (~2 dependencies) | No (Electron / Node) |
| Background removal | Yes (Built-in local) | No (Usually paid/cloud) |

---

## Screenshots

<div align="center">
  <img src="assets/compressly-darkmode.png" alt="Compressly Dark Mode" width="700" />
  <br/><em>Dark mode — Windows 11-inspired UI with sidebar navigation</em>
  <br/><br/>
  <img src="assets/compressly-lightmode.png" alt="Compressly Light Mode" width="700" />
  <br/><em>Light mode — clean, minimal interface</em>
</div>

---

## Features

- **Lightweight** — only two runtime dependencies (`PySide6` + `Pillow`)
- **Privacy-first** — 100% local processing, no network, no telemetry, no analytics
- **Fast** — multi-threaded batch compression that never blocks the UI
- **Modern UI** — Windows 11-inspired design with dark/light theme, smooth animations, sidebar navigation
- **Multi-format** — reads JPG, PNG, WebP, BMP, GIF, TIFF; writes JPG, PNG, WebP
- **Background Removal** — local AI-powered background removal (no cloud)
- **Format Converter** — convert between image formats in bulk
- **Folder Watch** — auto-compress images as they land in a watched folder
- **Compression History** — track all past compression sessions
- **Hardened** — atomic writes, decompression-bomb cap (200 MP), no `subprocess` shell, no `eval`

---

## Compression Presets

| Preset | Format | Quality | Resize | Best For |
|---|---|---|---|---|
| **Ultra Quality** | WebP | 95 | Original | Portfolios, print previews |
| **Balanced** | WebP | 82 | Original | General use (recommended) |
| **Web Optimized** | WebP | 78 | 1920px longest | Hero images, articles |
| **Maximum Compression** | WebP | 55 | 80% scale | Smallest possible files |

All presets are fully customisable from within the app.

---

## Project Structure

```
Compressly/
├── app/
│   ├── core/              # Folder watching, history, output naming
│   ├── engine/            # Pillow-backed compression (pure functions, no Qt)
│   │   ├── compressor.py  # Core compress_image() logic
│   │   └── bg_remove.py   # Local background removal
│   ├── workers/           # QThreadPool batch compression controller
│   ├── theme/             # QSS stylesheet + theme manager
│   ├── ui/                # All PySide6 widgets and pages
│   │   ├── main_window.py # Root application window
│   │   ├── sidebar.py     # Navigation sidebar
│   │   ├── dashboard.py   # Home/dashboard page
│   │   ├── pages.py       # Compression pages
│   │   ├── feature_pages.py  # Extra feature pages
│   │   ├── preview.py     # Image preview widget
│   │   ├── dropzone.py    # Drag-and-drop zone
│   │   ├── controls.py    # Shared UI controls
│   │   └── toast.py       # Toast notification system
│   ├── models.py          # Typed dataclasses (Preset, CompressionSettings…)
│   └── presets.py         # Built-in compression presets
├── assets/
│   ├── icon.ico           # Windows app icon (multi-size)
│   ├── icon.png           # 512 px source PNG
│   └── compressly-logo.png
├── scripts/               # Developer debug & smoke-test scripts
├── main.py                # App entry point
├── build.py               # PyInstaller build wrapper
├── setup.bat              # One-click setup & launch for end users
├── requirements.txt       # Runtime dependencies (pinned)
├── requirements-build.txt # Build-time dependencies
└── version_info.txt       # Windows version metadata for PyInstaller
```

---

## Getting Started

### Prerequisites

- **Python 3.10+** — [Download from python.org](https://www.python.org/downloads/)
  - Make sure to tick **"Add Python to PATH"** during installation

### Option 1 — One-Click Setup (Recommended for end users)

Double-click **`setup.bat`** in the project folder. It will:
1. Check that Python is installed
2. Create a `.venv` virtual environment
3. Install all dependencies
4. Launch Compressly automatically

### Option 2 — Manual Setup (Recommended for developers)

```powershell
# 1. Clone the repository
git clone https://github.com/AyaanplayszYT/Compressly.git
cd Compressly

# 2. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install runtime dependencies
pip install -r requirements.txt

# 4. Run the app
python main.py
```

---

## Building a Windows Executable

```powershell
# Activate your virtual environment first
.\.venv\Scripts\Activate.ps1

# Install build dependencies
pip install -r requirements-build.txt

# Build (one-folder — recommended, faster startup)
python build.py

# OR build a single .exe file
python build.py --onefile
```

Output lands in:
- **One-folder**: `dist/Compressly/Compressly.exe`
- **Single file**: `dist/Compressly.exe`

---

## Security

Compressly takes a hardened approach to security:

- **No shell injection** — zero use of `subprocess(shell=True)`, `eval`, or `exec` on user input
- **Atomic file writes** — output files use `tempfile.mkstemp` + `os.replace`, so interrupted runs never corrupt existing files
- **Decompression bomb protection** — `Image.MAX_IMAGE_PIXELS` capped at 200 megapixels
- **Defensive error handling** — all image opens are wrapped in try/except; corrupted files surface as per-file errors, not crashes
- **No symlink traversal** — symlinks are never followed when expanding folders
- **Zero network activity** — the app makes **no outbound network requests** whatsoever
- **Pinned dependencies** — `PySide6==6.8.1.1` and `Pillow==11.0.0`, both actively maintained and free of known critical CVEs

---

## Development & Testing

Debug and test scripts live in the `scripts/` folder:

```powershell
# Run the smoke test (engine-level, no GUI)
python scripts/smoke_test.py

# Run the GUI integration test
python scripts/gui_test.py
```

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| [PySide6](https://doc.qt.io/qtforpython/) | 6.8.1.1 | Qt 6 Python bindings — UI framework |
| [Pillow](https://python-pillow.org/) | 11.0.0 | Image I/O, encoding, and processing |
| [PyInstaller](https://pyinstaller.org/) *(build only)* | 6.11.1 | Packages the app into a Windows `.exe` |

---

## Contributing

Contributions are welcome! Here's how to get started:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes and commit: `git commit -m 'Add your feature'`
4. Push to your branch: `git push origin feature/your-feature-name`
5. Open a Pull Request

Please keep PRs focused and include a description of what was changed and why.

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  Made by <strong>Mistix</strong>
</div>
