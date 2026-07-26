import sqlite3
import os
import time

class DatabaseManager:
    """SQLite Database manager for tracking song review status, positions, and history."""
    
    def __init__(self, db_path="song.db"):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Songs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS songs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filepath TEXT UNIQUE NOT NULL,
                    title TEXT,
                    artist TEXT,
                    album TEXT,
                    duration REAL DEFAULT 0,
                    bitrate INTEGER DEFAULT 0,
                    file_size INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'unreviewed', -- 'unreviewed', 'kept', 'deleted', 'skipped'
                    last_position REAL DEFAULT 0,
                    is_duplicate INTEGER DEFAULT 0,
                    added_time REAL DEFAULT 0,
                    updated_at REAL DEFAULT 0
                )
            """)

            # History table for undo operations
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    song_id INTEGER NOT NULL,
                    filepath TEXT NOT NULL,
                    action TEXT NOT NULL, -- 'kept', 'deleted', 'skipped'
                    prev_status TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    FOREIGN KEY (song_id) REFERENCES songs (id) ON DELETE CASCADE
                )
            """)

            # Settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            conn.commit()

    def upsert_song(self, song_data):
        self.upsert_songs_batch([song_data])

    def upsert_songs_batch(self, songs_list):
        """Bulk insert or update a list of songs in a single transaction."""
        now = time.time()
        records = []
        for song_data in songs_list:
            records.append((
                song_data['filepath'],
                song_data.get('title', 'Unknown Title'),
                song_data.get('artist', 'Unknown Artist'),
                song_data.get('album', 'Unknown Album'),
                song_data.get('duration', 0.0),
                song_data.get('bitrate', 0),
                song_data.get('file_size', 0),
                song_data.get('is_duplicate', 0),
                song_data.get('added_time', now),
                now
            ))

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO songs (filepath, title, artist, album, duration, bitrate, file_size, is_duplicate, added_time, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(filepath) DO UPDATE SET
                    title = excluded.title,
                    artist = excluded.artist,
                    album = excluded.album,
                    duration = excluded.duration,
                    bitrate = excluded.bitrate,
                    file_size = excluded.file_size,
                    is_duplicate = excluded.is_duplicate,
                    updated_at = excluded.updated_at
            """, records)
            conn.commit()

    def update_song_status(self, filepath, new_status, log_history=True):
        """Update a song's status ('kept', 'deleted', 'skipped', 'unreviewed') and optionally log history."""
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, status FROM songs WHERE filepath = ?", (filepath,))
            row = cursor.fetchone()
            if not row:
                return False

            song_id, prev_status = row['id'], row['status']
            if prev_status == new_status:
                return True

            cursor.execute("""
                UPDATE songs SET status = ?, updated_at = ? WHERE id = ?
            """, (new_status, now, song_id))

            if log_history:
                cursor.execute("""
                    INSERT INTO history (song_id, filepath, action, prev_status, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (song_id, filepath, new_status, prev_status, now))

            conn.commit()
            return True

    def update_last_position(self, filepath, position_sec):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE songs SET last_position = ? WHERE filepath = ?", (position_sec, filepath))
            conn.commit()

    def get_song_by_path(self, filepath):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM songs WHERE filepath = ?", (filepath,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_songs(self, status_filter=None, bitrate_filter=None, unknown_artist_only=False, min_duration=None, duplicates_only=False):
        """Get filtered list of songs."""
        query = "SELECT * FROM songs WHERE 1=1"
        params = []

        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)

        if bitrate_filter:
            query += " AND bitrate >= ?"
            params.append(bitrate_filter)

        if unknown_artist_only:
            query += " AND (artist IS NULL OR LOWER(artist) LIKE '%unknown%')"

        if min_duration:
            query += " AND duration >= ?"
            params.append(min_duration)

        if duplicates_only:
            query += " AND is_duplicate = 1"

        query += " ORDER BY id ASC"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def undo_last_action(self):
        """Revert the most recent action in the history log."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM history ORDER BY id DESC LIMIT 1")
            last_entry = cursor.fetchone()
            if not last_entry:
                return None

            entry_dict = dict(last_entry)
            cursor.execute("UPDATE songs SET status = ? WHERE id = ?", (entry_dict['prev_status'], entry_dict['song_id']))
            cursor.execute("DELETE FROM history WHERE id = ?", (entry_dict['id'],))
            conn.commit()
            return entry_dict

    def get_history(self, limit=50):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT h.id, h.song_id, h.filepath, h.action, h.prev_status, h.timestamp, s.title, s.artist
                FROM history h
                JOIN songs s ON h.song_id = s.id
                ORDER BY h.id DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self):
        """Return counts for Kept, Deleted, Skipped, Unreviewed, and Total."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'kept' THEN 1 ELSE 0 END) as kept,
                    SUM(CASE WHEN status = 'deleted' THEN 1 ELSE 0 END) as deleted,
                    SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped,
                    SUM(CASE WHEN status = 'unreviewed' THEN 1 ELSE 0 END) as unreviewed
                FROM songs
            """)
            row = cursor.fetchone()
            return {
                'total': row['total'] or 0,
                'kept': row['kept'] or 0,
                'deleted': row['deleted'] or 0,
                'skipped': row['skipped'] or 0,
                'unreviewed': row['unreviewed'] or 0
            }

    def set_setting(self, key, value):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))
            conn.commit()

    def get_setting(self, key, default=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row['value'] if row else default
