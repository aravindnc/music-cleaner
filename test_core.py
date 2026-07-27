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

    def test_audio_player_state_reset(self):
        from audio_player import AudioPlayer
        from PySide6.QtCore import QCoreApplication
        import io, wave
        app = QCoreApplication.instance() or QCoreApplication([])

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
        # Default settings
        settings = self.db.get_all_settings()
        self.assertEqual(settings['volume'], '80')
        self.assertEqual(settings['delete_mode'], 'recycle_bin')

        # Custom settings set/get
        self.db.set_setting('volume', 90)
        self.db.set_setting('custom_start_sec', 15.5)

        self.assertEqual(self.db.get_setting('volume'), '90')
        self.assertEqual(self.db.get_setting('custom_start_sec'), '15.5')

        updated = self.db.get_all_settings()
        self.assertEqual(updated['volume'], '90')
        self.assertEqual(updated['custom_start_sec'], '15.5')

    def test_audio_player_volume_and_bytes(self):
        from audio_player import AudioPlayer
        from PySide6.QtCore import QCoreApplication
        import io, wave
        app = QCoreApplication.instance() or QCoreApplication([])

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

if __name__ == "__main__":
    unittest.main()
