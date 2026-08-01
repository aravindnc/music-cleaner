<p align="center">
  <img src="app_icon.png" alt="MusicCleaner Icon" width="128" height="128" />
</p>

# 🎵 MusicCleaner

> **Rapidly review, keep, or delete thousands of audio files with lightning-fast keyboard shortcuts.**

MusicCleaner is a high-speed desktop audio curation app designed to clean up large music collections (5,000 to 50,000+ tracks). Easily review 700–1,000 songs per hour without popups or mouse clicks.

<p align="center">
  <a href="https://github.com/aravindnc/music-cleaner/releases/latest">
    <img src="https://img.shields.io/badge/Download-MusicCleaner.exe%20(Windows)-blue?style=for-the-badge&logo=windows&logoColor=white" alt="Download MusicCleaner.exe" />
  </a>
</p>

---

## 😫 The Problem

If you have a massive music collection (10,000 to 50,000+ tracks) accumulated over years, organizing it manually is a nightmare:
- **Painfully Slow**: Standard media players force you to double-click, wait for audio to buffer, listen to 15s of silence/intros, alt-tab back, and manually delete files. At ~15 seconds per song, cleaning 30,000 tracks takes **125+ hours**.
- **Annoying Popups**: Existing tools prompt *"Are you sure you want to delete this file?"* every single time.
- **Clunky Duplicate Finders**: Most software only looks at file hashes or tags, failing to let you quickly audition tracks by ear.

**MusicCleaner solves this by giving you a Tinder-like experience for local audio files.** Review 700–1,000 songs per hour with instant audio playback, smart chorus previews, and single-key shortcuts (`K` to Keep, `D` to Delete, `S` to Skip).

---

## ✨ Features

- ⚡ **Lightning-Fast Playback**: Zero-delay song switching with background RAM pre-buffering.
- ⌨️ **Keyboard-Driven Workflow**: Single keypress to Keep, Delete, Skip, Seek, or Undo.
- 🎯 **Smart Preview Modes**: Jump straight to the action with 5 preview options (*Loudest Peak (Chorus)*, *Start of song*, *Custom Offset*, *Middle + 30s*, or *Random point*).
- 🌊 **Interactive Waveform**: Visual audio timeline with click, drag, and mouse-wheel seeking.
- 🗑️ **Safe Recycle Bin Deletion**: Deletes files safely to your OS Recycle Bin so nothing is lost permanently.
- 🔍 **Smart Filters & Duplicate Detection**: Quickly filter by *Unreviewed Only*, *Duplicates Only*, *320 kbps Only*, *Unknown Artist*, or *Longer than 7 min*.
- 📋 **Action History & Restore**: Live sidebar tracking recent decisions with single-click per-item **Restore** and instant **Undo** (`Ctrl+Z`).
- 💾 **Auto-Save Progress**: Automatically saves your curation state so you can close and resume anytime.

---

## 📖 How to Use

1. **Scan Folders**: Click `📁 Scan Folders` to select your music directory.
2. **Review Songs**: Use keyboard shortcuts to quickly organize your songs:

| Shortcut | Action |
| :--- | :--- |
| **`K` / `Enter`** | **Keep** song and move to next |
| **`D` / `Delete`** | **Delete** song (Move to Recycle Bin) |
| **`S`** | **Skip** song for later review |
| **`Space`** | Play / Pause playback |
| **`←` / `→`** | Seek -20s / +20s |
| **`Ctrl+←` / `Ctrl+→`** | Jump to Previous / Next song |
| **`1` – `9`** | Jump to 10% – 90% of track length |
| **`R`** | Restart song from 0:00 |
| **`Ctrl+Z`** | **Undo** last decision |

3. **Use Filters**: Filter your library using the top dropdown menu to focus on unreviewed tracks, duplicates, or specific quality criteria.

---

## 🚀 Getting Started

### Using the Standalone Executable (Windows)

1. **[Download `MusicCleaner.exe` from Latest Releases](https://github.com/aravindnc/music-cleaner/releases/latest)**
2. Double-click `MusicCleaner.exe` to launch. No installation required!

### Running from Source

```bash
# Clone the repository
git clone https://github.com/aravindnc/music-cleaner.git
cd music-cleaner

# Install dependencies
pip install -r requirements.txt

# Launch MusicCleaner
python main.py
```

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.
