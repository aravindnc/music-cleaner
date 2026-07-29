import unittest
import os
import shutil
import tempfile
from database import DatabaseManager
from metadata_service import extract_metadata, detect_duplicates
from trash_service import TrashService

class TestSongReviewerCore(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_song.db")
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_database_crud_and_statistics(self):
        song1 = {
            'filepath': os.path.join(self.temp_dir, 'song1.mp3'),
            'title': 'Test Song 1',
            'artist': 'Artist A',
            'album': 'Album A',
            'duration': 240.0,
            'bitrate': 320,
            'file_size': 5000000
        }
        song2 = {
            'filepath': os.path.join(self.temp_dir, 'song2.mp3'),
            'title': 'Test Song 2',
            'artist': 'Unknown Artist',
            'album': 'Album B',
            'duration': 180.0,
            'bitrate': 128,
            'file_size': 3000000
        }

        self.db.upsert_song(song1)
        self.db.upsert_song(song2)

        songs = self.db.get_songs()
        self.assertEqual(len(songs), 2)

        # Update status
        self.db.update_song_status(song1['filepath'], 'kept')
        self.db.update_song_status(song2['filepath'], 'deleted')

        stats = self.db.get_statistics()
        self.assertEqual(stats['kept'], 1)
        self.assertEqual(stats['deleted'], 1)
        self.assertEqual(stats['unreviewed'], 0)

        # Undo last action
        undone = self.db.undo_last_action()
        self.assertIsNotNone(undone)
        self.assertEqual(undone['action'], 'deleted')

        stats_after_undo = self.db.get_statistics()
        self.assertEqual(stats_after_undo['deleted'], 0)

    def test_restore_specific_history_entry(self):
        song1 = {'filepath': os.path.join(self.temp_dir, 's1.mp3'), 'title': 'S1'}
        self.db.upsert_song(song1)
        self.db.update_song_status(song1['filepath'], 'kept')
        self.db.update_song_status(song1['filepath'], 'deleted')

        history = self.db.get_history()
        self.assertEqual(len(history), 2)
        
        # Restore specific history entry (the latest deleted entry)
        latest_entry = history[0]
        restored = self.db.restore_history_entry(latest_entry['id'])
        self.assertIsNotNone(restored)
        self.assertEqual(restored['action'], 'deleted')

        updated_song = self.db.get_song_by_path(song1['filepath'])
        self.assertEqual(updated_song['status'], 'kept')

    def test_audio_player_state_reset(self):
        from audio_player import AudioPlayer
        from PySide6.QtWidgets import QApplication
        import io, wave
        app = QApplication.instance() or QApplication([])

        player = AudioPlayer()
        # Test nonexistent file return value
        res = player.load_song(os.path.join(self.temp_dir, "nonexistent.mp3"))
        self.assertFalse(res)

        # Test in-memory buffer load
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(44100)
            wf.writeframes(b'\x00\x00' * 44100)
        buf.seek(0)
        res_buf = player.load_song("virtual_path.wav", file_buffer=buf)
        self.assertTrue(res_buf)

        # Test pause state reset on stop
        player._is_paused = True
        player.stop()
        self.assertFalse(player._is_paused)
        self.assertFalse(player.is_playing_state)

    def test_database_settings(self):
        import configparser

        # Default settings
        settings = self.db.get_all_settings()
        self.assertEqual(settings['volume'], '80')
        self.assertEqual(settings['delete_mode'], 'recycle_bin')

        # Setting default values should NOT write to INI file (save custom settings only)
        self.db.set_setting('volume', 80)
        ini_config = configparser.ConfigParser()
        ini_config.read(self.db.ini_path)
        self.assertFalse(ini_config.has_section('Settings') and 'volume' in ini_config['Settings'])

        # Custom settings set/get
        self.db.set_setting('volume', 90)
        self.db.set_setting('custom_start_sec', 15.5)

        self.assertEqual(self.db.get_setting('volume'), '90')
        self.assertEqual(self.db.get_setting('custom_start_sec'), '15.5')

        updated = self.db.get_all_settings()
        self.assertEqual(updated['volume'], '90')
        self.assertEqual(updated['custom_start_sec'], '15.5')

        # Verify only custom settings are saved in the INI file
        ini_config = configparser.ConfigParser()
        ini_config.read(self.db.ini_path)
        self.assertIn('volume', ini_config['Settings'])
        self.assertIn('custom_start_sec', ini_config['Settings'])
        self.assertNotIn('delete_mode', ini_config['Settings'])

        # Reset custom setting back to default value -> removes key from INI
        self.db.set_setting('volume', 80)
        ini_config2 = configparser.ConfigParser()
        ini_config2.read(self.db.ini_path)
        self.assertNotIn('volume', ini_config2['Settings'])
        self.assertEqual(self.db.get_setting('volume'), '80')

    def test_audio_player_volume_and_bytes(self):
        from audio_player import AudioPlayer
        from PySide6.QtWidgets import QApplication
        import io, wave
        app = QApplication.instance() or QApplication([])

        player = AudioPlayer()
        player.set_volume(50)
        self.assertEqual(player.get_volume(), 50)

        # Test raw bytes buffer load
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(44100)
            wf.writeframes(b'\x00\x00' * 44100)
        raw_bytes = buf.getvalue()

        res_bytes = player.load_song("virtual_path.wav", file_buffer=raw_bytes)
        self.assertTrue(res_bytes)

    def test_next_song_random(self):
        from unittest.mock import MagicMock
        from main_window import MainWindow
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        # Create window without running full UI
        window = MainWindow()
        window.playlist = [{'filepath': f'song{i}.mp3'} for i in range(10)]
        window.upcoming_queue = list(range(10))
        window.current_index = 0
        window.load_song_at_index = MagicMock()

        window.next_song()
        self.assertTrue(0 <= window.current_index < 10)
        window.load_song_at_index.assert_called_once_with(window.current_index)

    def test_responsive_cover_and_details(self):
        from main_window import MainWindow
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        window = MainWindow()

        # Test initial responsiveness at standard resolution
        window.resize(1200, 800)
        window.update_cover_and_details_responsive()
        cover_w1200 = window.cover_label.width()

        # Test responsiveness on small resolution
        window.resize(800, 600)
        window.update_cover_and_details_responsive()
        cover_w800 = window.cover_label.width()

        self.assertLess(cover_w800, cover_w1200)

    def test_auto_skip_on_playback_issue(self):
        from unittest.mock import MagicMock
        from main_window import MainWindow
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        window = MainWindow()
        window.playlist = [{'filepath': f'invalid_path_{i}.mp3'} for i in range(5)]
        window.upcoming_queue = [1, 2, 3, 4]
        window.current_index = 0
        window.consecutive_play_errors = 0
        window.next_song = MagicMock()

        # Trigger load_song_at_index on an unplayable file path
        window.load_song_at_index(0)
        self.assertGreater(window.consecutive_play_errors, 0)

        # Trigger playback error handler directly
        window.on_playback_error("Test playback error")
        self.assertGreater(window.consecutive_play_errors, 1)

if __name__ == "__main__":
    unittest.main()
