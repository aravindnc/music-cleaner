import os
import sys
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtCore import QUrl

try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    HAS_QT_MULTIMEDIA = True
except ImportError:
    HAS_QT_MULTIMEDIA = False

try:
    import pygame
    pygame.mixer.init()
    HAS_PYGAME = True
except Exception as e:
    HAS_PYGAME = False

try:
    import vlc
    # Test if libvlc DLL actually exists on system
    _test_inst = vlc.Instance('--no-video', '--quiet')
    HAS_VLC = True
except Exception:
    HAS_VLC = False

class AudioPlayer(QObject):
    """Audio player supporting VLC and Pygame mixer audio engines."""

    position_changed = Signal(float)  # current time in seconds
    duration_changed = Signal(float)  # total duration in seconds
    playback_ended = Signal()
    state_changed = Signal(bool)       # True if playing, False if paused

    def __init__(self, parent=None):
        super().__init__(parent)
        self.use_vlc = HAS_VLC
        self.use_pygame = HAS_PYGAME and not HAS_VLC
        self.current_filepath = None
        self.is_playing_state = False
        self._duration = 0.0
        self.start_pos_offset = 0.0

        if self.use_vlc:
            try:
                self.vlc_instance = vlc.Instance('--no-video', '--quiet')
                self.vlc_player = self.vlc_instance.media_player_new()
                
                self.timer = QTimer(self)
                self.timer.setInterval(100)
                self.timer.timeout.connect(self._poll_vlc_position)
            except Exception as e:
                print(f"VLC initialization failed: {e}")
                self.use_vlc = False
                self.use_pygame = HAS_PYGAME

        if self.use_pygame or not self.use_vlc:
            self.timer = QTimer(self)
            self.timer.setInterval(100)
            self.timer.timeout.connect(self._poll_pygame_position)




    def load_song(self, filepath, start_position=0.0):
        self.stop()
        self.current_filepath = filepath

        if not os.path.exists(filepath):
            return False

        if self.use_vlc:
            media = self.vlc_instance.media_new(filepath)
            self.vlc_player.set_media(media)
            if start_position > 0:
                self._pending_start_pos = start_position
            else:
                self._pending_start_pos = None
        elif HAS_PYGAME:
            try:
                pygame.mixer.music.load(filepath)
                self.start_pos_offset = start_position
            except Exception as e:
                print(f"Pygame load error: {e}")

        return True

    def play(self):
        if not self.current_filepath:
            return

        if self.use_vlc:
            self.vlc_player.play()
            self.timer.start()
            if hasattr(self, '_pending_start_pos') and self._pending_start_pos:
                QTimer.singleShot(150, lambda: self.seek(self._pending_start_pos))
                self._pending_start_pos = None
        elif HAS_PYGAME:
            try:
                pygame.mixer.music.play(start=self.start_pos_offset)
                self.timer.start()
            except Exception as e:
                print(f"Pygame play error: {e}")

        self.is_playing_state = True
        self.state_changed.emit(True)

    def pause(self):
        if self.use_vlc:
            self.vlc_player.pause()
            self.timer.stop()
        elif HAS_PYGAME:
            pygame.mixer.music.pause()
            self.timer.stop()

        self.is_playing_state = False
        self.state_changed.emit(False)

    def toggle_play_pause(self):
        if self.is_playing_state:
            self.pause()
        else:
            self.play()

    def stop(self):
        if self.use_vlc:
            self.vlc_player.stop()
            self.timer.stop()
        elif HAS_PYGAME:
            pygame.mixer.music.stop()
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass
            self.timer.stop()

        self.is_playing_state = False
        self.state_changed.emit(False)

    def seek(self, position_sec):
        if position_sec < 0:
            position_sec = 0

        if self.use_vlc:
            length = self.vlc_player.get_length() / 1000.0
            if length > 0:
                pos_fraction = max(0.0, min(1.0, position_sec / length))
                self.vlc_player.set_position(pos_fraction)
        elif HAS_PYGAME:
            self.start_pos_offset = position_sec
            if self.is_playing_state:
                try:
                    pygame.mixer.music.play(start=position_sec)
                except Exception:
                    pass

        self.position_changed.emit(position_sec)

    def get_position(self):
        if self.use_vlc:
            ms = self.vlc_player.get_time()
            return max(0.0, ms / 1000.0) if ms >= 0 else 0.0
        elif HAS_PYGAME:
            get_pos = pygame.mixer.music.get_pos()  # milliseconds since play() called
            if get_pos >= 0:
                return self.start_pos_offset + (get_pos / 1000.0)
            return self.start_pos_offset
        return 0.0

    def get_duration(self):
        if self.use_vlc:
            ms = self.vlc_player.get_length()
            return max(0.0, ms / 1000.0) if ms >= 0 else 0.0
        return self._duration

    def _poll_vlc_position(self):
        if not self.use_vlc:
            return

        pos = self.get_position()
        dur = self.get_duration()

        if dur > 0 and dur != self._duration:
            self._duration = dur
            self.duration_changed.emit(dur)

        self.position_changed.emit(pos)

        state = self.vlc_player.get_state()
        if state == vlc.State.Ended:
            self.stop()
            self.playback_ended.emit()

    def _poll_pygame_position(self):
        if not self.use_pygame:
            return

        pos = self.get_position()
        self.position_changed.emit(pos)

        if not pygame.mixer.music.get_busy() and self.is_playing_state:
            self.stop()
            self.playback_ended.emit()

    def _on_qt_duration_changed(self, dur_ms):
        dur_sec = dur_ms / 1000.0
        self._duration = dur_sec
        self.duration_changed.emit(dur_sec)

    def _on_qt_state_changed(self, state):
        if state == QMediaPlayer.StoppedState and self.get_position() >= self.get_duration() - 0.5:
            self.is_playing_state = False
            self.state_changed.emit(False)
            self.playback_ended.emit()
