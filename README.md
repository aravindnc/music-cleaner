# 🎵 MusicCleaner (Fast Song Reviewer)

> **Rapidly review, keep, or delete thousands of MP3s with keyboard shortcuts.**

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![UI Framework](https://img.shields.io/badge/PySide6-Qt6-green.svg)](https://pypi.org/project/PySide6/)

MusicCleaner is a high-speed desktop audio curation application for collectors with large music libraries (5,000 to 50,000+ tracks). Review **700–1,000 songs per hour** without confirmation popups or mouse clicks.

---

## ⚡ Key Features

- **Super-Fast Keyboard Workflow**:
  - `K` → Keep song & auto-advance.
  - `D` → Move song to Windows Recycle Bin & auto-advance.
  - `S` → Skip song & auto-advance.
  - `Space` → Play / Pause.
  - `←` / `→` → Seek -20s / +20s.
  - `Ctrl+←` / `Ctrl+→` → Previous / Next song.
  - `1` – `9` → Jump to 10% – 90% of song length.
  - `R` → Restart song.
  - `Ctrl+Z` → Undo last action.
- **Smart Audio Previews**: Skip boring intros with 3 preview modes (Start, Middle + 30s, or Random Point).
- **Interactive Waveform Slider**: Visual audio waveform with click, drag, and mouse-wheel seeking.
- **Automatic Resume (SQLite)**: Automatically saves progress (`song.db`) so you can resume anytime.
- **Safe Recycle Bin Deletion**: Uses `send2trash` so deleted files can be restored anytime.
- **Decision History & Undo Drawer**: Side panel showing your last 50 decisions with 1-click Undo.
- **Instant Large Library Support**: Loads 10,000+ songs in under 0.5 seconds using bulk transaction batching.

---

## 📦 Download Standalone Executable (Windows)

No Python installation required! 

1. Go to the [**Releases**](https://github.com/your-username/music-cleaner/releases) page.
2. Download `MusicCleaner.exe`.
3. Double-click to run!

---

## 🚀 Quick Start (From Source)

### 1. Installation

Clone the repository and install requirements:

```bash
git clone https://github.com/your-username/music-cleaner.git
cd music-cleaner
pip install -r requirements.txt
```

### 2. Launching the App

```bash
python main.py
```

---

## 🔨 How to Build Standalone `.exe` (Auto-Versioning)

To build your executable (which automatically bumps the patch version e.g. `1.0.0` -> `1.0.1` and embeds Windows metadata):

1. Run the build script:
   ```bash
   python build.py
   ```

2. Your output file will be saved to:
   > `dist/MusicCleaner.exe`

*(You can also build manually using `py -3 -m PyInstaller --noconsole --onefile --icon=app_icon.ico --add-data "app_icon.ico;." --version-file=file_version_info.txt --name=MusicCleaner main.py`)*

---

## 🛠 Tech Stack

- **Python 3.10+**
- **PySide6** (Qt6 Desktop Interface)
- **pygame.mixer / python-vlc** (Audio Playback Engine)
- **mutagen** (Audio Metadata Parsing & Artwork Extraction)
- **Send2Trash** (Windows Recycle Bin Safe Deletion)
- **SQLite** (Session Progress & Decision Log)

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.
