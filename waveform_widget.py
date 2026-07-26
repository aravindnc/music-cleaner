import random
import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush

class WaveformWidget(QWidget):
    """Custom interactive waveform timeline widget supporting drag, click, and wheel seeking."""

    seek_requested = Signal(float)  # Position in seconds

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(64)
        self.setMouseTracking(True)
        
        self.duration = 100.0  # seconds
        self.current_position = 0.0  # seconds
        self.is_dragging = False
        self.waveform_samples = self._generate_dummy_waveform()

    def set_duration(self, duration):
        self.duration = max(0.1, duration)
        self.update()

    def set_position(self, position):
        if not self.is_dragging:
            self.current_position = max(0.0, min(self.duration, position))
            self.update()

    def set_waveform_data(self, samples):
        if len(samples) > 0:
            self.waveform_samples = samples
        else:
            self.waveform_samples = self._generate_dummy_waveform()
        self.update()

    def _generate_dummy_waveform(self, count=120):
        """Generate a realistic random audio waveform shape."""
        random.seed(42)
        samples = []
        for i in range(count):
            # Smooth envelope curve
            envelope = np.sin(np.pi * i / count)
            val = random.uniform(0.15, 0.95) * envelope + 0.05
            samples.append(min(1.0, max(0.05, val)))
        return samples

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self._handle_mouse_seek(event.position().x())

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self._handle_mouse_seek(event.position().x())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_dragging:
            self.is_dragging = False
            self._handle_mouse_seek(event.position().x())

    def wheelEvent(self, event):
        """Scroll wheel seek: 2 seconds per notch."""
        delta = event.angleDelta().y()
        step = 2.0 if delta > 0 else -2.0
        new_pos = max(0.0, min(self.duration, self.current_position + step))
        self.current_position = new_pos
        self.seek_requested.emit(new_pos)
        self.update()

    def _handle_mouse_seek(self, mouse_x):
        width = self.width()
        if width > 0:
            fraction = max(0.0, min(1.0, mouse_x / width))
            pos_sec = fraction * self.duration
            self.current_position = pos_sec
            self.seek_requested.emit(pos_sec)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()

        # Background
        painter.fillRect(0, 0, width, height, QColor("#1e1e24"))

        # Progress calculation
        progress_ratio = max(0.0, min(1.0, self.current_position / self.duration))
        progress_x = width * progress_ratio

        # Waveform Bars
        num_bars = len(self.waveform_samples)
        bar_gap = 2
        total_gaps = (num_bars - 1) * bar_gap
        bar_width = max(2.0, (width - total_gaps) / num_bars)

        mid_y = height / 2.0

        for i, val in enumerate(self.waveform_samples):
            x = i * (bar_width + bar_gap)
            bar_h = val * (height - 16)
            y = mid_y - (bar_h / 2.0)

            # Color past vs future
            if x + bar_width <= progress_x:
                color = QColor("#00adb5")  # Played accent teal
            elif x < progress_x:
                color = QColor("#00adb5")
            else:
                color = QColor("#393e46")  # Unplayed grey

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(QRectF(x, y, bar_width, bar_h), 2, 2)

        # Scrubber Line & Knob
        painter.setPen(QPen(QColor("#00fff5"), 2))
        painter.drawLine(int(progress_x), 0, int(progress_x), height)

        painter.setBrush(QBrush(QColor("#00fff5")))
        painter.drawEllipse(QRectF(progress_x - 5, mid_y - 5, 10, 10))
