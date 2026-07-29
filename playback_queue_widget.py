import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

class PlaybackQueueWidget(QWidget):
    """Sidebar widget displaying upcoming audio files in the queue for playback."""

    song_selected = Signal(int)  # emits playlist index
    undo_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(260)
        self.setMaximumWidth(340)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel("🎶 Up Next (Queue)")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #eeeeee;")
        
        self.undo_btn = QPushButton("↺ Undo")
        self.undo_btn.setToolTip("Undo Last Action (Ctrl+Z)")
        self.undo_btn.setStyleSheet("""
            QPushButton {
                background-color: #393e46;
                color: #00adb5;
                border: 1px solid #00adb5;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #00adb5;
                color: #222831;
            }
        """)
        self.undo_btn.clicked.connect(self.undo_requested.emit)

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.undo_btn)
        layout.addLayout(header_layout)

        # Subtitle
        self.sub_label = QLabel("Upcoming songs for playback:")
        self.sub_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        layout.addWidget(self.sub_label)

        # Queue List Widget
        self.queue_list = QListWidget()
        self.queue_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e24;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                background-color: #2b2b36;
                border-radius: 4px;
                margin-bottom: 4px;
                padding: 4px;
                color: #dddddd;
            }
            QListWidget::item:hover {
                background-color: #393e46;
                border: 1px solid #00adb5;
            }
            QListWidget::item:selected {
                background-color: #00adb5;
                color: #ffffff;
            }
        """)
        self.queue_list.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.queue_list)

    def on_item_clicked(self, item):
        playlist_idx = item.data(Qt.UserRole)
        if playlist_idx is not None:
            self.song_selected.emit(playlist_idx)

    def populate_queue(self, upcoming_items, total_remaining=0):
        """
        upcoming_items: list of tuples (playlist_index, song_dict), max 10 entries
        """
        self.queue_list.clear()
        count = len(upcoming_items)
        if total_remaining > count:
            self.sub_label.setText(f"Next {count} in queue ({total_remaining} total left):")
        else:
            self.sub_label.setText(f"Upcoming in queue ({count}):")

        if not upcoming_items:
            empty_item = QListWidgetItem("No more songs in queue")
            empty_item.setFlags(Qt.NoItemFlags)
            self.queue_list.addItem(empty_item)
            return

        for i, (playlist_idx, song) in enumerate(upcoming_items, start=1):
            title = song.get('title') or os.path.basename(song['filepath'])
            artist = song.get('artist') or "Unknown Artist"
            album = song.get('album') or "Unknown Album"
            duration = song.get('duration', 0.0)

            dur_str = ""
            if duration > 0:
                m = int(duration // 60)
                s = int(duration % 60)
                dur_str = f" ({m:02d}:{s:02d})"

            widget = QWidget()
            h_layout = QHBoxLayout(widget)
            h_layout.setContentsMargins(4, 4, 4, 4)
            h_layout.setSpacing(6)

            # Queue position badge
            num_label = QLabel(f"#{i}")
            num_label.setFixedWidth(24)
            num_label.setAlignment(Qt.AlignCenter)
            num_label.setStyleSheet("color: #00adb5; font-weight: bold; font-size: 11px;")
            h_layout.addWidget(num_label)

            # Thumbnail label
            thumb_label = QLabel()
            thumb_label.setFixedSize(38, 38)
            thumb_label.setAlignment(Qt.AlignCenter)

            cover_bytes = song.get('cover_art_bytes')
            loaded_pix = False
            if cover_bytes:
                pix = QPixmap()
                if pix.loadFromData(cover_bytes):
                    scaled_pix = pix.scaled(38, 38, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    thumb_label.setPixmap(scaled_pix)
                    thumb_label.setStyleSheet("border-radius: 4px; background-color: #111;")
                    loaded_pix = True

            if not loaded_pix:
                thumb_label.setText("🎵")
                thumb_label.setStyleSheet("background-color: #1a1c23; color: #00adb5; font-size: 15px; border-radius: 4px; border: 1px solid #333;")

            h_layout.addWidget(thumb_label)

            # Song details column
            v_layout = QVBoxLayout()
            v_layout.setSpacing(2)
            v_layout.setContentsMargins(0, 0, 0, 0)

            title_lbl = QLabel(f"{title}{dur_str}")
            title_lbl.setStyleSheet("font-weight: 600; font-size: 11px; color: #eeeeee;")
            title_lbl.setTextInteractionFlags(Qt.NoTextInteraction)

            meta_lbl = QLabel(f"{artist} • {album}")
            meta_lbl.setStyleSheet("color: #888888; font-size: 10px;")
            meta_lbl.setTextInteractionFlags(Qt.NoTextInteraction)

            v_layout.addWidget(title_lbl)
            v_layout.addWidget(meta_lbl)

            h_layout.addLayout(v_layout, 1)

            list_item = QListWidgetItem(self.queue_list)
            list_item.setSizeHint(widget.sizeHint())
            list_item.setData(Qt.UserRole, playlist_idx)
            self.queue_list.addItem(list_item)
            self.queue_list.setItemWidget(list_item, widget)
