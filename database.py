import sqlite3
import os
import time
import configparser

class DatabaseManager:
    """SQLite Database manager for tracking song review status, positions, and history."""
    
    DEFAULT_SETTINGS = {
        'volume': '80',
        'preview_mode': 'Loudest Peak (Chorus)',
        'custom_start_sec': '0.0',
        'auto_skip_enabled': 'False',
        'auto_skip_sec': '15',
        'delete_mode': 'recycle_bin',
    }

    def __init__(self, db_path="song.db", ini_path=None):
        self.db_path = db_path
        if ini_path:
            self.ini_path = ini_path
        else:
            base_dir = os.path.dirname(os.path.abspath(db_path)) if db_path else os.getcwd()
            self.ini_path = os.path.join(base_dir, "settings.ini")
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

    def restore_history_entry(self, history_id):
        """Revert a specific decision history entry back to its previous status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM history WHERE id = ?", (history_id,))
            row = cursor.fetchone()
            if not row:
                return None

            entry_dict = dict(row)
            cursor.execute("UPDATE songs SET status = ?, updated_at = ? WHERE id = ?", 
                           (entry_dict['prev_status'], time.time(), entry_dict['song_id']))
            cursor.execute("DELETE FROM history WHERE id = ?", (history_id,))
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

    def _read_ini(self):
        config = configparser.ConfigParser()
        config.optionxform = str  # Preserve key case
        if os.path.exists(self.ini_path):
            config.read(self.ini_path, encoding='utf-8')
        return config

    def _write_ini(self, config):
        with open(self.ini_path, 'w', encoding='utf-8') as f:
            config.write(f)

    def set_setting(self, key, value):
        config = self._read_ini()
        if 'Settings' not in config:
            config['Settings'] = {}

        val_str = str(value)
        default_val = self.DEFAULT_SETTINGS.get(key)

        # Save custom settings only (if value equals default, remove from INI)
        if default_val is not None and val_str == str(default_val):
            if key in config['Settings']:
                del config['Settings'][key]
        else:
            config['Settings'][key] = val_str

        # If Settings section is empty, clean it up or remove file if empty
        if not config['Settings']:
            config.remove_section('Settings')

        self._write_ini(config)

    def get_setting(self, key, default=None):
        config = self._read_ini()
        if 'Settings' in config and key in config['Settings']:
            return config['Settings'][key]
        return self.DEFAULT_SETTINGS.get(key, default)

    def get_all_settings(self):
        """Retrieve all settings as a dict with default fallbacks."""
        settings = dict(self.DEFAULT_SETTINGS)
        config = self._read_ini()
        if 'Settings' in config:
            for key, val in config['Settings'].items():
                settings[key] = val
        return settings


