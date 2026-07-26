import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QListWidget, QListWidgetItem, QFrame)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QColor

class DecisionHistoryWidget(QWidget):
    """Sidebar widget displaying decision history and enabling single-click undo."""

    undo_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(260)
        self.setMaximumWidth(320)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel("📋 Decision History")
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
        sub_label = QLabel("Last 50 decisions:")
        sub_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        layout.addWidget(sub_label)

        # History List
        self.history_list = QListWidget()
        self.history_list.setStyleSheet("""
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
                padding: 6px;
                color: #dddddd;
            }
            QListWidget::item:hover {
                background-color: #393e46;
            }
        """)
        layout.addWidget(self.history_list)

    def populate_history(self, history_entries):
        self.history_list.clear()

        for item in history_entries:
            action = item['action']
            title = item.get('title') or os.path.basename(item['filepath'])
            artist = item.get('artist') or "Unknown Artist"

            if action == 'kept':
                icon = "✓"
                badge_style = "color: #4eef90;"
                text_action = "KEEP"
            elif action == 'deleted':
                icon = "🗑"
                badge_style = "color: #ff5555;"
                text_action = "DELETE"
            else:  # skipped
                icon = "⏭"
                badge_style = "color: #ffb86c;"
                text_action = "SKIP"

            widget = QWidget()
            w_layout = QVBoxLayout(widget)
            w_layout.setContentsMargins(2, 2, 2, 2)
            w_layout.setSpacing(2)

            top_line = QLabel(f"<span style='{badge_style} font-weight:bold;'>{icon} {text_action}</span> - {title}")
            top_line.setTextFormat(Qt.RichText)
            top_line.setStyleSheet("font-size: 12px;")
            top_line.setWordWrap(True)

            sub_line = QLabel(artist)
            sub_line.setStyleSheet("font-size: 10px; color: #888888;")

            w_layout.addWidget(top_line)
            w_layout.addWidget(sub_line)

            list_item = QListWidgetItem(self.history_list)
            list_item.setSizeHint(QSize(220, 48))
            self.history_list.addItem(list_item)
            self.history_list.setItemWidget(list_item, widget)
