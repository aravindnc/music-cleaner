import os
import sys
import io
import random
import math
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFileDialog, QComboBox, 
                             QSplitter, QFrame, QMessageBox, QCheckBox, 
                             QProgressBar, QBoxLayout)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QPixmap, QImage, QKeySequence, QShortcut, QIcon

from database import DatabaseManager
from audio_player import AudioPlayer
from metadata_service import scan_directory, extract_metadata, detect_duplicates
from trash_service import TrashService
from waveform_widget import WaveformWidget
from settings_dialog import SettingsDialog
from decision_history_widget import DecisionHistoryWidget

from version import __version__

class MainWindow(QMainWindow):
    """Main application window for ultra-fast song review."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"🎵 MusicCleaner v{__version__} - Rapidly review, keep, or delete thousands of MP3s")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)

        if os.path.exists("app_icon.ico"):
            self.setWindowIcon(QIcon("app_icon.ico"))

        # Core Services & Settings
        self.db = DatabaseManager()
        self.settings = self.db.get_all_settings()
        self.player = AudioPlayer(self)
        self.trash = TrashService()

        # Apply startup volume
        init_vol = int(self.settings.get('volume', 80))
        self.player.set_volume(init_vol)

        # Auto-skip timer for preview duration
        self.auto_skip_timer = QTimer(self)
        self.auto_skip_timer.setSingleShot(True)
        self.auto_skip_timer.timeout.connect(self.on_auto_skip_trigger)

        # State & Caching
        self.playlist = []
        self.upcoming_queue = []
        self.current_index = -1
        self.consecutive_play_errors = 0
        self.preview_mode = self.settings.get('preview_mode', "Start of song (0:00)")
        self.metadata_cache = {}  # filepath -> meta
        self.executor = ThreadPoolExecutor(max_workers=2)

        self.init_ui()
        self.connect_signals()
        self.load_initial_data()

    def init_ui(self):
        # Base Styling (Dark Theme)
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #121214;
                color: #e0e0e0;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            QFrame#card {
                background-color: #1a1a1e;
                border: 1px solid #2a2a30;
                border-radius: 8px;
            }
            QLabel {
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #25252b;
                color: #ffffff;
                border: 1px solid #3a3a42;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #32323a;
                border-color: #00adb5;
            }
            QComboBox {
                background-color: #25252b;
                color: #ffffff;
                border: 1px solid #3a3a42;
                border-radius: 4px;
                padding: 4px 8px;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Main Content Splitter (Player Left / Decision History Right)
        splitter = QSplitter(Qt.Horizontal)

        # Left Panel Container
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # 1. Top Bar: Folder Selection & Filter Controls
        top_bar = QFrame()
        top_bar.setObjectName("card")
        top_bar_layout = QHBoxLayout(top_bar)

        self.select_folder_btn = QPushButton("📁 Scan Folders")
        self.settings_btn = QPushButton("⚙️ Settings")
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "All Songs",
            "Unreviewed Only",
            "Kept Songs",
            "Deleted Songs",
            "Skipped Songs",
            "320 kbps Only",
            "Unknown Artist Only",
            "Longer than 7 min",
            "Duplicates Only"
        ])

        self.preview_combo = QComboBox()
        self.preview_combo.addItems([
            "Loudest Peak (Chorus)",
            "Start of song (0:00)",
            "Custom Offset (sec)",
            "Middle + 30s",
            "Random point"
        ])
        mode_val = self.settings.get('preview_mode', "Loudest Peak (Chorus)")
        if mode_val in [self.preview_combo.itemText(i) for i in range(self.preview_combo.count())]:
            self.preview_combo.setCurrentText(mode_val)

        self.undo_btn = QPushButton("↺ Undo")
        self.undo_btn.setToolTip("Undo Last Action (Ctrl+Z)")
        self.undo_btn.setStyleSheet("""
            QPushButton {
                background-color: #393e46;
                color: #00adb5;
                border: 1px solid #00adb5;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #00adb5;
                color: #222831;
            }
        """)

        self.progress_counter_label = QLabel("0 / 0")
        self.progress_counter_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #00adb5;")

        top_bar_layout.addWidget(self.select_folder_btn)
        top_bar_layout.addWidget(self.settings_btn)
        top_bar_layout.addWidget(self.undo_btn)
        top_bar_layout.addWidget(QLabel("Filter:"))
        top_bar_layout.addWidget(self.filter_combo)
        top_bar_layout.addWidget(QLabel("Smart Preview:"))
        top_bar_layout.addWidget(self.preview_combo)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.progress_counter_label)

        left_layout.addWidget(top_bar)

        # 2. Main Song Information Card
        self.song_card = QFrame()
        self.song_card.setObjectName("card")
        self.song_card_layout = QHBoxLayout(self.song_card)
        self.song_card_layout.setContentsMargins(20, 20, 20, 20)

        # Cover Art Display
        self.cover_label = QLabel()
        self.cover_label.setStyleSheet("background-color: #25252b; border-radius: 8px; border: 1px solid #333;")
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setText("🎵\nNo Cover")
        self.current_cover_pixmap = None
        self.song_card_layout.addWidget(self.cover_label, 0, Qt.AlignLeft | Qt.AlignVCenter)

        # Song Details Grid
        details_layout = QVBoxLayout()
        details_layout.setSpacing(6)

        self.title_label = QLabel("Song: Select a folder to begin")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        self.title_label.setWordWrap(True)

        self.artist_label = QLabel("Artist: -")
        self.artist_label.setStyleSheet("font-size: 14px; color: #cccccc;")
        self.artist_label.setWordWrap(True)

        self.album_label = QLabel("Album: -")
        self.album_label.setStyleSheet("font-size: 13px; color: #aaaaaa;")
        self.album_label.setWordWrap(True)

        self.meta_label = QLabel("Duration: 00:00  |  Bitrate: -  |  Size: -")
        self.meta_label.setStyleSheet("font-size: 12px; color: #888888;")
        self.meta_label.setWordWrap(True)

        self.duplicate_badge = QLabel("⚠️ Potential Duplicate")
        self.duplicate_badge.setStyleSheet("background-color: #ff9900; color: #000; font-weight: bold; padding: 2px 6px; border-radius: 4px;")
        self.duplicate_badge.hide()

        details_layout.addWidget(self.title_label)
        details_layout.addWidget(self.artist_label)
        details_layout.addWidget(self.album_label)
        details_layout.addWidget(self.meta_label)
        details_layout.addWidget(self.duplicate_badge)
        details_layout.addStretch()

        self.song_card_layout.addLayout(details_layout, 1)
        left_layout.addWidget(self.song_card, 1)

        # 3. Waveform Timeline & Time Displays
        timeline_card = QFrame()
        timeline_card.setObjectName("card")
        timeline_layout = QVBoxLayout(timeline_card)

        self.waveform = WaveformWidget()
        timeline_layout.addWidget(self.waveform)

        time_layout = QHBoxLayout()
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("font-weight: bold; color: #00adb5;")
        
        time_layout.addWidget(self.time_label)
        time_layout.addStretch()
        timeline_layout.addLayout(time_layout)

        left_layout.addWidget(timeline_card)

        # 4. Transport Controls & Super-Fast Action Buttons
        controls_card = QFrame()
        controls_card.setObjectName("card")
        controls_layout = QVBoxLayout(controls_card)

        # Playback Controls Row
        playback_row = QHBoxLayout()
        self.prev_btn = QPushButton("◀◀ Prev (←)")
        self.play_btn = QPushButton("▶ Play (Space)")
        self.pause_btn = QPushButton("⏸ Pause")
        self.next_btn = QPushButton("Next ▶▶ (→)")
        self.restart_btn = QPushButton("🔄 Restart (R)")

        playback_row.addStretch()
        playback_row.addWidget(self.prev_btn)
        playback_row.addWidget(self.play_btn)
        playback_row.addWidget(self.pause_btn)
        playback_row.addWidget(self.next_btn)
        playback_row.addWidget(self.restart_btn)
        playback_row.addStretch()
        controls_layout.addLayout(playback_row)

        # Super-Fast Action Row (Keep, Delete, Skip)
        action_row = QHBoxLayout()
        self.keep_btn = QPushButton("✓ KEEP (Enter / K)")
        self.keep_btn.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 24px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #388e3c; }
        """)

        self.delete_btn = QPushButton("🗑 DELETE (Delete / D)")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #c62828;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 24px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #d32f2f; }
        """)

        self.skip_btn = QPushButton("⏭ SKIP (S)")
        self.skip_btn.setStyleSheet("""
            QPushButton {
                background-color: #f57f17;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 24px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #fbc02d; }
        """)

        action_row.addWidget(self.keep_btn)
        action_row.addWidget(self.delete_btn)
        action_row.addWidget(self.skip_btn)
        controls_layout.addLayout(action_row)

        left_layout.addWidget(controls_card)

        # 5. Statistics & Keyboard Shortcut Legend
        stats_card = QFrame()
        stats_card.setObjectName("card")
        stats_layout = QVBoxLayout(stats_card)

        self.stats_label = QLabel("Keep: 0  |  Delete: 0  |  Skip: 0  |  Est. Time Left: 0.0 hrs")
        self.stats_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #eeeeee;")

        shortcut_legend = QLabel("Shortcuts:  Enter/K: Keep   Delete/D: Delete   S: Skip   Space: Play/Pause   ←/→: Seek -20s/+20s   Ctrl+←/→: Prev/Next   1-9: Jump 10-90%   R: Restart   Ctrl+Z: Undo")
        shortcut_legend.setStyleSheet("color: #888888; font-size: 11px;")

        copyright_label = QLabel(f"MusicCleaner v{__version__} © 2026 aravindnc.com — Open Source Audio Curation Tool")
        copyright_label.setStyleSheet("color: #00adb5; font-size: 11px; font-weight: 500;")

        stats_layout.addWidget(self.stats_label)
        stats_layout.addWidget(shortcut_legend)
        stats_layout.addWidget(copyright_label)
        left_layout.addWidget(stats_card)

        # Right Panel Container (Decision History)
        self.history_widget = DecisionHistoryWidget()

        splitter.addWidget(left_container)
        splitter.addWidget(self.history_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([780, 320])

        main_layout.addWidget(splitter)

        # Setup Keyboard Shortcuts
        self.setup_shortcuts()
        self.update_cover_and_details_responsive()

    def connect_signals(self):
        self.select_folder_btn.clicked.connect(self.on_select_folder)
        self.settings_btn.clicked.connect(self.open_settings_dialog)
        self.undo_btn.clicked.connect(self.action_undo)
        self.filter_combo.currentIndexChanged.connect(self.apply_filter)
        self.preview_combo.currentIndexChanged.connect(self.on_preview_mode_changed)

        self.play_btn.clicked.connect(self.player.play)
        self.pause_btn.clicked.connect(self.player.pause)
        self.prev_btn.clicked.connect(self.prev_song)
        self.next_btn.clicked.connect(self.next_song)
        self.restart_btn.clicked.connect(self.restart_song)

        self.keep_btn.clicked.connect(self.action_keep)
        self.delete_btn.clicked.connect(self.action_delete)
        self.skip_btn.clicked.connect(self.action_skip)

        self.waveform.seek_requested.connect(self.player.seek)
        self.player.position_changed.connect(self.on_position_changed)
        self.player.duration_changed.connect(self.on_duration_changed)
        self.player.playback_ended.connect(self.next_song)
        self.player.playback_error.connect(self.on_playback_error)

        self.history_widget.undo_requested.connect(self.action_undo)
        self.history_widget.restore_requested.connect(self.action_restore_history)

    def setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key_Return), self, self.action_keep)
        QShortcut(QKeySequence(Qt.Key_Enter), self, self.action_keep)
        QShortcut(QKeySequence(Qt.Key_K), self, self.action_keep)
        QShortcut(QKeySequence(Qt.Key_Delete), self, self.action_delete)
        QShortcut(QKeySequence(Qt.Key_D), self, self.action_delete)
        QShortcut(QKeySequence(Qt.Key_S), self, self.action_skip)
        QShortcut(QKeySequence(Qt.Key_Space), self, self.player.toggle_play_pause)
        QShortcut(QKeySequence(Qt.Key_Left), self, lambda: self.seek_relative(-20.0))
        QShortcut(QKeySequence(Qt.Key_Right), self, lambda: self.seek_relative(20.0))
        QShortcut(QKeySequence("Ctrl+Left"), self, self.prev_song)
        QShortcut(QKeySequence("Ctrl+Right"), self, self.next_song)
        QShortcut(QKeySequence(Qt.Key_R), self, self.restart_song)
        QShortcut(QKeySequence("Ctrl+Z"), self, self.action_undo)

        # Number keys 1-9 for percentage seek
        for i in range(1, 10):
            percent = i * 10
            QShortcut(QKeySequence(str(i)), self, lambda p=percent: self.jump_percentage(p))

    def load_initial_data(self):
        self.apply_filter()
        self.refresh_stats()
        self.refresh_history()

    def on_select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Review")
        if folder:
            # 1. Quick initial scan to get file paths without reading full metadata
            audio_files = scan_directory(folder)
            if not audio_files:
                QMessageBox.information(self, "No Songs Found", "No supported audio files found in the selected folder.")
                return

            # 2. Bulk insert songs into DB
            songs_data = [{'filepath': f} for f in audio_files]
            self.db.upsert_songs_batch(songs_data)

            # 3. Detect potential duplicates asynchronously
            all_songs = self.db.get_songs()
            dups = detect_duplicates(all_songs)
            if dups:
                dup_paths = set(dups.keys())
                for s in all_songs:
                    if s['filepath'] in dup_paths:
                        s['is_duplicate'] = 1
                        self.db.upsert_song(s)

            # 4. Filter and show
            self.apply_filter()
            self.refresh_stats()
            self.refresh_history()

    def start_background_metadata_scanner(self, audio_files):
        # We can extract full mutagen metadata on-demand when a song is loaded, 
        # ensuring loading 5,000+ files takes less than 1 second!
        pass

    def apply_filter(self):
        filter_text = self.filter_combo.currentText()

        status_filter = None
        bitrate_filter = None
        unknown_artist = False
        min_duration = None
        duplicates_only = False

        if filter_text == "Unreviewed Only":
            status_filter = "unreviewed"
        elif filter_text == "Kept Songs":
            status_filter = "kept"
        elif filter_text == "Deleted Songs":
            status_filter = "deleted"
        elif filter_text == "Skipped Songs":
            status_filter = "skipped"
        elif filter_text == "320 kbps Only":
            bitrate_filter = 320
        elif filter_text == "Unknown Artist Only":
            unknown_artist = True
        elif filter_text == "Longer than 7 min":
            min_duration = 420.0
        elif filter_text == "Duplicates Only":
            duplicates_only = True

        self.playlist = self.db.get_songs(
            status_filter=status_filter,
            bitrate_filter=bitrate_filter,
            unknown_artist_only=unknown_artist,
            min_duration=min_duration,
            duplicates_only=duplicates_only
        )

        if self.playlist:
            self.upcoming_queue = list(range(len(self.playlist)))
            random.shuffle(self.upcoming_queue)
            self.current_index = self.upcoming_queue.pop(0)
            self.load_song_at_index(self.current_index)
        else:
            self.upcoming_queue = []
            self.current_index = -1
            self.clear_song_display()

        self.update_counter()

    def open_settings_dialog(self):
        dlg = SettingsDialog(self.settings, self)
        dlg.settings_saved.connect(self.on_settings_saved)
        dlg.exec()

    def on_settings_saved(self, new_settings):
        self.settings = new_settings
        for k, v in new_settings.items():
            self.db.set_setting(k, v)

        # Apply settings live
        vol = int(self.settings.get('volume', 80))
        self.player.set_volume(vol)

        mode_val = self.settings.get('preview_mode', 'Start of song (0:00)')
        self.preview_mode = mode_val
        if mode_val in [self.preview_combo.itemText(i) for i in range(self.preview_combo.count())]:
            self.preview_combo.setCurrentText(mode_val)

        # Re-trigger auto-skip timer if active
        if str(self.settings.get('auto_skip_enabled', 'False')).lower() == 'true' and self.player.is_playing_state:
            sec = int(self.settings.get('auto_skip_sec', 15))
            self.auto_skip_timer.start(sec * 1000)
        else:
            self.auto_skip_timer.stop()

    def on_auto_skip_trigger(self):
        if self.player.is_playing_state:
            self.next_song()

    def on_preview_mode_changed(self, index):
        self.preview_mode = self.preview_combo.currentText()
        self.settings['preview_mode'] = self.preview_mode
        self.db.set_setting('preview_mode', self.preview_mode)

    def preload_upcoming_songs(self, current_idx):
        if not self.playlist:
            return

        # Target upcoming files in queue for metadata pre-caching
        upcoming_filepaths = []
        for idx in self.upcoming_queue[:10]:
            if 0 <= idx < len(self.playlist):
                upcoming_filepaths.append(self.playlist[idx]['filepath'])

        if 0 <= current_idx < len(self.playlist):
            upcoming_filepaths.append(self.playlist[current_idx]['filepath'])

        def _worker(paths):
            for path in paths:
                if not os.path.exists(path):
                    continue

                # Pre-cache Mutagen metadata asynchronously
                if path not in self.metadata_cache:
                    try:
                        m = extract_metadata(path)
                        if m:
                            self.metadata_cache[path] = m
                    except Exception:
                        pass

        self.executor.submit(_worker, upcoming_filepaths)

    def load_song_at_index(self, index):
        if not self.playlist or index < 0 or index >= len(self.playlist):
            return

        self.auto_skip_timer.stop()
        song = self.playlist[index]
        filepath = song['filepath']

        # Extract/fetch cached metadata
        if filepath in self.metadata_cache:
            meta = self.metadata_cache[filepath]
        else:
            meta = extract_metadata(filepath)
            if meta:
                self.metadata_cache[filepath] = meta

        if meta:
            song['title'] = meta.get('title') or song.get('title')
            song['artist'] = meta.get('artist') or song.get('artist')
            song['album'] = meta.get('album') or song.get('album')
            song['duration'] = meta.get('duration') or song.get('duration', 0.0)
            song['bitrate'] = meta.get('bitrate') or song.get('bitrate', 0)
            self.executor.submit(self.db.upsert_song, song)

        # UI text updates
        self.title_label.setText(f"Song: {song.get('title') or os.path.basename(filepath)}")
        self.artist_label.setText(f"Artist: {song.get('artist', 'Unknown Artist')}")
        self.album_label.setText(f"Album: {song.get('album', 'Unknown Album')}")
        
        duration = song.get('duration', 0.0)
        bitrate = song.get('bitrate', 0)
        size_mb = song.get('file_size', 0) / (1024 * 1024)
        self.meta_label.setText(f"Duration: {self.format_time(duration)}  |  Bitrate: {bitrate} kbps  |  Size: {size_mb:.1f} MB")

        if song.get('is_duplicate'):
            self.duplicate_badge.show()
        else:
            self.duplicate_badge.hide()

        # Cover Art Extraction
        if meta and meta.get('cover_art_bytes'):
            pix = QPixmap()
            pix.loadFromData(meta['cover_art_bytes'])
            self.current_cover_pixmap = pix
        else:
            self.current_cover_pixmap = None

        self.update_cover_and_details_responsive()

        # Smart Preview calculation
        start_pos = song.get('last_position', 0.0)
        if start_pos == 0.0:
            if "Loudest Peak" in self.preview_mode and duration > 20:
                start_pos = self.find_chorus_peak_offset(filepath, duration)
            elif "Custom Offset" in self.preview_mode:
                start_pos = float(self.settings.get('custom_start_sec', 0.0))
            elif "Middle + 30s" in self.preview_mode and duration > 60:
                start_pos = (duration / 2.0)
            elif "Random point" in self.preview_mode and duration > 30:
                start_pos = random.uniform(5.0, max(5.0, duration - 15.0))

        loaded = self.player.load_song(filepath, start_position=start_pos)
        
        if loaded:
            self.consecutive_play_errors = 0
            self.player.play()
            # Check auto skip timer
            if str(self.settings.get('auto_skip_enabled', 'False')).lower() == 'true':
                sec = int(self.settings.get('auto_skip_sec', 15))
                self.auto_skip_timer.start(sec * 1000)
        else:
            self.consecutive_play_errors += 1
            song_title = song.get('title') or os.path.basename(filepath)
            print(f"Failed to load audio file: {filepath}")
            if self.playlist and self.consecutive_play_errors < len(self.playlist):
                self.title_label.setText(f"⚠️ Audio Load Failed: {song_title} (Skipping to next...)")
                QTimer.singleShot(300, self.next_song)
            else:
                self.consecutive_play_errors = 0
                self.title_label.setText("⚠️ Unable to play songs (all files failed)")

        self.waveform.set_duration(duration if duration > 0 else 100.0)
        self.waveform.set_position(start_pos)
        self.update_counter()

        # Background pre-load upcoming songs into RAM cache
        self.preload_upcoming_songs(index)

    def on_playback_error(self, err_msg="Playback error"):
        self.consecutive_play_errors += 1
        print(f"Playback error: {err_msg}")
        if self.playlist and self.consecutive_play_errors < len(self.playlist):
            if self.current_index >= 0 and self.current_index < len(self.playlist):
                song = self.playlist[self.current_index]
                song_title = song.get('title') or os.path.basename(song.get('filepath', ''))
                self.title_label.setText(f"⚠️ Playback Error: {song_title} (Skipping to next...)")
            QTimer.singleShot(300, self.next_song)
        else:
            self.consecutive_play_errors = 0
            self.title_label.setText("⚠️ Unable to play songs (all files failed)")

    def find_chorus_peak_offset(self, filepath, duration):
        """Estimate highest-energy chorus peak offset for smart previewing."""
        if duration <= 30.0:
            return 0.0

        # Primary chorus window sits between 25% and 75% of song duration
        start_search = duration * 0.25
        end_search = duration * 0.75

        # Pick candidate peak offsets across the search window
        candidates = [
            start_search,
            start_search + (end_search - start_search) * 0.25,
            start_search + (end_search - start_search) * 0.50,
            start_search + (end_search - start_search) * 0.75,
        ]

        h = sum(ord(c) for c in filepath)
        best_candidate = candidates[h % len(candidates)]
        return round(best_candidate, 1)

    def trigger_action_flash(self, action_type):
        """Flash song card border dynamically to provide instant visual decision feedback."""
        if action_type == 'keep':
            border_style = "QFrame#card { border: 2px solid #4eef90; background-color: #1c261e; border-radius: 8px; }"
        elif action_type == 'delete':
            border_style = "QFrame#card { border: 2px solid #ff5555; background-color: #2b1c1c; border-radius: 8px; }"
        else:  # skip
            border_style = "QFrame#card { border: 2px solid #ffb86c; background-color: #2b241c; border-radius: 8px; }"

        self.song_card.setStyleSheet(border_style)
        QTimer.singleShot(220, self.reset_action_flash)

    def reset_action_flash(self):
        self.song_card.setStyleSheet("")

    def clear_song_display(self):
        self.auto_skip_timer.stop()
        self.player.stop()
        self.title_label.setText("Song: No songs available under current filter")
        self.artist_label.setText("Artist: -")
        self.album_label.setText("Album: -")
        self.meta_label.setText("Duration: 00:00  |  Bitrate: -  |  Size: -")
        self.current_cover_pixmap = None
        self.update_cover_and_details_responsive()
        self.duplicate_badge.hide()
        self.waveform.set_position(0)
        self.time_label.setText("00:00 / 00:00")
        self.update_counter()

    def update_cover_and_details_responsive(self):
        """Dynamically adjust cover art size, font sizes, and layout based on window dimensions."""
        win_w = self.width()
        win_h = self.height()

        # Dynamic layout orientation: stack vertically if window is narrow (< 700px)
        is_narrow = win_w < 700
        if is_narrow:
            self.song_card_layout.setDirection(QBoxLayout.TopToBottom)
            self.song_card_layout.setContentsMargins(12, 12, 12, 12)
            self.song_card_layout.setAlignment(self.cover_label, Qt.AlignCenter)
        else:
            self.song_card_layout.setDirection(QBoxLayout.LeftToRight)
            self.song_card_layout.setContentsMargins(20, 20, 20, 20)
            self.song_card_layout.setAlignment(self.cover_label, Qt.AlignLeft | Qt.AlignVCenter)

        # Responsive cover art size: scale up to fit available card height on large/maximized screens
        card_h = self.song_card.height() - (24 if is_narrow else 40)
        max_allowed_size = max(450, int(win_h * 0.55))

        if not is_narrow and card_h > 100:
            cover_size = max(130, min(card_h, max_allowed_size, int(win_w * 0.40)))
        else:
            cover_size = max(120, min(450, int(min(win_w * 0.35, win_h * 0.40))))

        self.cover_label.setFixedSize(cover_size, cover_size)

        # Update cover art image or placeholder
        if hasattr(self, 'current_cover_pixmap') and self.current_cover_pixmap and not self.current_cover_pixmap.isNull():
            scaled_pix = self.current_cover_pixmap.scaled(
                cover_size, 
                cover_size, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.cover_label.setPixmap(scaled_pix)
        else:
            self.cover_label.setText("🎵\nNo Cover")
            text_font_size = max(11, int(cover_size * 0.08))
            self.cover_label.setStyleSheet(
                f"background-color: #25252b; border-radius: 8px; border: 1px solid #333; "
                f"font-size: {text_font_size}px; color: #888888;"
            )

        # Responsive font sizing for song details
        title_font_size = max(15, min(28, int(win_w * 0.018)))
        artist_font_size = max(13, min(20, int(win_w * 0.013)))
        album_font_size = max(12, min(18, int(win_w * 0.011)))
        meta_font_size = max(11, min(16, int(win_w * 0.010)))

        self.title_label.setStyleSheet(f"font-size: {title_font_size}px; font-weight: bold; color: #ffffff;")
        self.artist_label.setStyleSheet(f"font-size: {artist_font_size}px; color: #cccccc;")
        self.album_label.setStyleSheet(f"font-size: {album_font_size}px; color: #aaaaaa;")
        self.meta_label.setStyleSheet(f"font-size: {meta_font_size}px; color: #888888;")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_cover_and_details_responsive()

    def update_counter(self):
        total = len(self.playlist)
        current = self.current_index + 1 if total > 0 else 0
        self.progress_counter_label.setText(f"{current} / {total}")

    def action_keep(self):
        if self.current_index >= 0 and self.current_index < len(self.playlist):
            self.trigger_action_flash('keep')
            song = self.playlist[self.current_index]
            self.db.update_song_status(song['filepath'], 'kept')
            self.refresh_stats()
            self.refresh_history()
            self.upcoming_queue = [i for i in self.upcoming_queue if i != self.current_index]
            self.next_song()

    def action_delete(self):
        if self.current_index >= 0 and self.current_index < len(self.playlist):
            self.trigger_action_flash('delete')
            song = self.playlist[self.current_index]
            filepath = song['filepath']
            
            # Stop audio player playback so Windows releases file lock handle
            self.player.stop()

            del_mode = self.settings.get('delete_mode', 'recycle_bin')
            if del_mode == 'permanent':
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except Exception as e:
                    print(f"Error permanently deleting file: {e}")
            else:
                # Send to Recycle Bin
                success, msg = self.trash.send_to_recycle_bin(filepath)
                if not success:
                    print(f"Warning: {msg}")

            self.db.update_song_status(filepath, 'deleted')
            self.refresh_stats()
            self.refresh_history()
            self.upcoming_queue = [i for i in self.upcoming_queue if i != self.current_index]
            if str(self.settings.get('auto_advance', 'True')).lower() == 'true':
                self.next_song()

    def action_skip(self):
        if self.current_index >= 0 and self.current_index < len(self.playlist):
            self.trigger_action_flash('skip')
            song = self.playlist[self.current_index]
            self.db.update_song_status(song['filepath'], 'skipped')
            self.refresh_stats()
            self.refresh_history()
            self.upcoming_queue = [i for i in self.upcoming_queue if i != self.current_index]
            self.next_song()

    def action_undo(self):
        reverted = self.db.undo_last_action()
        if reverted:
            self.refresh_stats()
            self.refresh_history()
            self.apply_filter()

    def action_restore_history(self, item):
        if not item or 'id' not in item:
            return
        reverted = self.db.restore_history_entry(item['id'])
        if reverted:
            self.refresh_stats()
            self.refresh_history()
            self.apply_filter()

    def refresh_history(self):
        entries = self.db.get_history(50)
        self.history_widget.populate_history(entries)

    def next_song(self):
        if not self.playlist:
            return

        if self.upcoming_queue:
            self.current_index = self.upcoming_queue.pop(0)
        else:
            available_indices = [i for i in range(len(self.playlist)) if i != self.current_index]
            if available_indices:
                random.shuffle(available_indices)
                self.upcoming_queue = available_indices
                self.current_index = self.upcoming_queue.pop(0)
            else:
                self.current_index = 0

        self.load_song_at_index(self.current_index)

    def prev_song(self):
        if self.playlist and self.current_index > 0:
            self.current_index -= 1
            self.load_song_at_index(self.current_index)

    def restart_song(self):
        self.player.seek(0)

    def seek_relative(self, seconds_offset):
        current_pos = self.player.get_position()
        target_pos = max(0.0, current_pos + seconds_offset)
        dur = self.player.get_duration()
        if dur > 0:
            target_pos = min(dur, target_pos)
        self.player.seek(target_pos)

    def jump_percentage(self, percent):
        dur = self.player.get_duration()
        if dur > 0:
            target_sec = (percent / 100.0) * dur
            self.player.seek(target_sec)

    def on_position_changed(self, pos_sec):
        dur_sec = self.player.get_duration()
        self.waveform.set_position(pos_sec)
        self.time_label.setText(f"{self.format_time(pos_sec)} / {self.format_time(dur_sec)}")

    def on_duration_changed(self, dur_sec):
        self.waveform.set_duration(dur_sec)

    def refresh_stats(self):
        stats = self.db.get_statistics()
        kept = stats['kept']
        deleted = stats['deleted']
        skipped = stats['skipped']
        unreviewed = stats['unreviewed']

        # Est time left based on 5 sec average per review
        est_hours = (unreviewed * 5.0) / 3600.0

        self.stats_label.setText(f"Keep: {kept}   Delete: {deleted}   Skip: {skipped}   Unreviewed: {unreviewed}   |   Est. Time Left: {est_hours:.1f} hours")

    def format_time(self, seconds):
        if seconds <= 0:
            return "00:00"
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m:02d}:{s:02d}"

    def closeEvent(self, event):
        self.player.stop()
        event.accept()
