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

    def test_duplicate_detection(self):
        songs = [
            {'filepath': '/path/song1.mp3', 'title': 'Oru Pushpam', 'artist': 'Yesudas'},
            {'filepath': '/path/song2.mp3', 'title': 'Oru Pushpam', 'artist': 'Yesudas'},
            {'filepath': '/path/song3.mp3', 'title': 'Unique Song', 'artist': 'Other'}
        ]
        duplicates = detect_duplicates(songs)
        self.assertIn('/path/song1.mp3', duplicates)
        self.assertIn('/path/song2.mp3', duplicates)
        self.assertNotIn('/path/song3.mp3', duplicates)

if __name__ == "__main__":
    unittest.main()
