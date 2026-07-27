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
        self._is_paused = False
        self._duration = 0.0
        self.start_pos_offset = 0.0
        self._play_grace_ticks = 0
        self._pending_start_pos = None
        self._current_buffer = None
        self._current_vlc_media = None
        self.volume_pct = 80

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

    def set_volume(self, volume_pct):
        """Set playback volume (0 to 100)."""
        self.volume_pct = max(0, min(100, int(volume_pct)))
        if self.use_vlc:
            try:
                self.vlc_player.audio_set_volume(self.volume_pct)
            except Exception as e:
                print(f"VLC volume set error: {e}")
        elif self.use_pygame:
            try:
                pygame.mixer.music.set_volume(self.volume_pct / 100.0)
            except Exception as e:
                print(f"Pygame volume set error: {e}")

    def get_volume(self):
        """Get playback volume (0 to 100)."""
        if self.use_vlc:
            try:
                v = self.vlc_player.audio_get_volume()
                if v >= 0:
                    return v
            except Exception:
                pass
        return self.volume_pct

    def load_song(self, filepath, start_position=0.0, file_buffer=None):
        self.stop()
        self.current_filepath = filepath
        self._pending_start_pos = start_position if start_position > 0 else None

        if not os.path.exists(filepath) and file_buffer is None:
            print(f"File not found: {filepath}")
            return False

        if self.use_vlc:
            loaded_ok = False
            
            # Prioritize direct file loading when file exists on disk
            if os.path.exists(filepath):
                try:
                    norm_path = os.path.normpath(filepath)
                    media = self.vlc_instance.media_new(norm_path)
                    self._current_vlc_media = media
                    self.vlc_player.set_media(media)
                    loaded_ok = True
                except Exception as e:
                    print(f"VLC path load error ({e}), trying buffer fallback...")

            # Fallback to file buffer if file path load failed or file doesn't exist on disk (e.g. virtual stream)
            if not loaded_ok and file_buffer is not None:
                try:
                    import io, ctypes
                    if isinstance(file_buffer, bytes):
                        raw_data = file_buffer
                    elif hasattr(file_buffer, 'getvalue'):
                        raw_data = file_buffer.getvalue()
                    else:
                        file_buffer.seek(0)
                        raw_data = file_buffer.read()

                    stream = io.BytesIO(raw_data)
                    stream_len = len(raw_data)

                    @vlc.CallbackDecorators.LD_OPEN
                    def open_cb(opaque, data_pointer, size_pointer):
                        size_pointer.contents.value = stream_len
                        stream.seek(0)
                        return 0

                    @vlc.CallbackDecorators.LD_READ
                    def read_cb(opaque, buf_ptr, count):
                        data = stream.read(count)
                        if data:
                            ctypes.memmove(buf_ptr, data, len(data))
                            return len(data)
                        return 0

                    @vlc.CallbackDecorators.LD_SEEK
                    def seek_cb(opaque, offset):
                        stream.seek(offset)
                        return 0

                    @vlc.CallbackDecorators.LD_CLOSE
                    def close_cb(opaque):
                        pass

                    media = self.vlc_instance.media_new_callbacks(open_cb, read_cb, seek_cb, close_cb, None)
                    # Retain media reference on self to prevent Python GC from unbinding ctypes callbacks
                    media._cb_refs = (open_cb, read_cb, seek_cb, close_cb, stream)
                    self._current_vlc_media = media
                    self.vlc_player.set_media(media)
                    loaded_ok = True
                except Exception as e:
                    print(f"VLC buffer load failed: {e}")

            if not loaded_ok:
                return False

            self.set_volume(self.volume_pct)
            return True

        elif self.use_pygame:
            norm_path = os.path.normpath(filepath)
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass

            loaded_ok = False

            # Prioritize direct file path loading when file exists on disk
            if os.path.exists(norm_path):
                import time
                for attempt in range(3):
                    try:
                        pygame.mixer.music.load(norm_path)
                        loaded_ok = True
                        break
                    except Exception as e:
                        time.sleep(0.05)
                if not loaded_ok:
                    print(f"Pygame load error for path {filepath}")

            # Fallback to buffer loading if path load failed or virtual stream
            if not loaded_ok and file_buffer is not None:
                raw_data = None
                if isinstance(file_buffer, bytes):
                    raw_data = file_buffer
                elif hasattr(file_buffer, 'getvalue'):
                    raw_data = file_buffer.getvalue()
                else:
                    try:
                        file_buffer.seek(0)
                        raw_data = file_buffer.read()
                    except Exception:
                        pass

                if raw_data:
                    try:
                        import io
                        self._current_buffer = io.BytesIO(raw_data)
                        ext_clean = os.path.splitext(filepath)[1].lower().lstrip('.')
                        hints = [h for h in [ext_clean, 'mp3', 'wav', 'ogg'] if h]

                        for hint in hints:
                            try:
                                self._current_buffer.seek(0)
                                pygame.mixer.music.load(self._current_buffer, hint)
                                loaded_ok = True
                                break
                            except Exception:
                                continue
                    except Exception as e:
                        print(f"BytesIO buffer load failed ({e})")

            if not loaded_ok:
                return False

            self.set_volume(self.volume_pct)
            self.start_pos_offset = start_position
            return True

        return False

    def play(self):
        if not self.current_filepath:
            return

        self._is_paused = False

        if self.use_vlc:
            self.vlc_player.play()
            self.timer.start()
        elif self.use_pygame:
            try:
                if self.start_pos_offset > 0:
                    try:
                        pygame.mixer.music.play(start=self.start_pos_offset)
                    except Exception as e:
                        print(f"Pygame start offset failed ({e}), playing from 0:00")
                        self.start_pos_offset = 0.0
                        pygame.mixer.music.play()
                else:
                    pygame.mixer.music.play()
                
                self._play_grace_ticks = 4  # 400ms grace period for Pygame init
                self.timer.start()
            except Exception as e:
                print(f"Pygame play error: {e}")
                self.is_playing_state = False
                self.state_changed.emit(False)
                return

        self.is_playing_state = True
        self.state_changed.emit(True)

    def pause(self):
        if self.use_vlc:
            self.vlc_player.pause()
            self.timer.stop()
        elif self.use_pygame:
            pygame.mixer.music.pause()
            self._is_paused = True
            self.timer.stop()

        self.is_playing_state = False
        self.state_changed.emit(False)

    def toggle_play_pause(self):
        if self.is_playing_state and not self._is_paused:
            self.pause()
        else:
            if self._is_paused and self.use_pygame:
                pygame.mixer.music.unpause()
                self._is_paused = False
                self.is_playing_state = True
                self.timer.start()
                self.state_changed.emit(True)
            else:
                self.play()

    def stop(self):
        if self.use_vlc:
            self.vlc_player.stop()
            self.timer.stop()
        elif self.use_pygame:
            pygame.mixer.music.stop()
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass
            self.timer.stop()

        self._is_paused = False
        self.is_playing_state = False
        self._current_buffer = None
        self.state_changed.emit(False)

    def seek(self, position_sec):
        if position_sec < 0:
            position_sec = 0

        if self.use_vlc:
            length = self.vlc_player.get_length() / 1000.0
            if length > 0:
                pos_fraction = max(0.0, min(1.0, position_sec / length))
                self.vlc_player.set_position(pos_fraction)
        elif self.use_pygame:
            self.start_pos_offset = position_sec
            if self.is_playing_state:
                try:
                    pygame.mixer.music.play(start=position_sec)
                    self._play_grace_ticks = 4
                except Exception as e:
                    print(f"Pygame seek error: {e}")

        self.position_changed.emit(position_sec)

    def get_position(self):
        if self.use_vlc:
            ms = self.vlc_player.get_time()
            return max(0.0, ms / 1000.0) if ms >= 0 else 0.0
        elif self.use_pygame:
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

        if dur > 0:
            if dur != self._duration:
                self._duration = dur
                self.duration_changed.emit(dur)

            if self._pending_start_pos is not None:
                pending = self._pending_start_pos
                self._pending_start_pos = None
                self.seek(pending)

        self.position_changed.emit(pos)

        state = self.vlc_player.get_state()
        if state in (vlc.State.Ended, vlc.State.Error):
            self.stop()
            self.playback_ended.emit()

    def _poll_pygame_position(self):
        if not self.use_pygame:
            return

        pos = self.get_position()
        self.position_changed.emit(pos)

        if self._play_grace_ticks > 0:
            self._play_grace_ticks -= 1
            return

        if self.is_playing_state and not pygame.mixer.music.get_busy():
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

