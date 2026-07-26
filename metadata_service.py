import os
import time
import mutagen
from mutagen.id3 import ID3, APIC
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from PySide6.QtGui import QImage, QPixmap

AUDIO_EXTENSIONS = {'.mp3', '.flac', '.m4a', '.mp4', '.wav', '.ogg', '.aac', '.wma', '.opus', '.aiff'}

def is_audio_file(filepath):
    _, ext = os.path.splitext(filepath)
    return ext.lower() in AUDIO_EXTENSIONS

def extract_metadata(filepath):
    """Extract metadata including duration, bitrate, artist, album, title, and cover art."""
    data = {
        'filepath': os.path.abspath(filepath),
        'title': os.path.basename(filepath),
        'artist': 'Unknown Artist',
        'album': 'Unknown Album',
        'duration': 0.0,
        'bitrate': 0,
        'file_size': 0,
        'cover_art_bytes': None,
        'added_time': os.path.getmtime(filepath) if os.path.exists(filepath) else time.time()
    }

    try:
        data['file_size'] = os.path.getsize(filepath)
        audio = mutagen.File(filepath)

        if audio is not None:
            # Duration
            if hasattr(audio.info, 'length') and audio.info.length:
                data['duration'] = float(audio.info.length)

            # Bitrate
            if hasattr(audio.info, 'bitrate') and audio.info.bitrate:
                data['bitrate'] = int(audio.info.bitrate // 1000)  # kbps

            # Metadata tags extraction
            tags = audio.tags
            if tags:
                # Title
                for key in ['TIT2', 'title', 'TITLE']:
                    if key in tags:
                        val = tags[key]
                        data['title'] = str(val[0]) if isinstance(val, list) else str(val)
                        break

                # Artist
                for key in ['TPE1', 'artist', 'ARTIST']:
                    if key in tags:
                        val = tags[key]
                        data['artist'] = str(val[0]) if isinstance(val, list) else str(val)
                        break

                # Album
                for key in ['TALB', 'album', 'ALBUM']:
                    if key in tags:
                        val = tags[key]
                        data['album'] = str(val[0]) if isinstance(val, list) else str(val)
                        break

                # Cover Art
                # ID3 APIC
                if isinstance(tags, ID3):
                    for tag in tags.values():
                        if isinstance(tag, APIC):
                            data['cover_art_bytes'] = tag.data
                            break
                elif hasattr(audio, 'pictures') and audio.pictures:
                    # FLAC / OGG pictures
                    data['cover_art_bytes'] = audio.pictures[0].data
                elif 'covr' in tags and tags['covr']:
                    # MP4 / M4A cover art
                    data['cover_art_bytes'] = bytes(tags['covr'][0])

    except Exception as e:
        print(f"Error parsing metadata for {filepath}: {e}")

    return data

def scan_directory(directory):
    """Recursively scan a directory for supported audio files."""
    audio_files = []
    if not os.path.exists(directory):
        return audio_files

    for root, _, files in os.walk(directory):
        for file in files:
            if is_audio_file(file):
                full_path = os.path.join(root, file)
                audio_files.append(full_path)

    return audio_files

def detect_duplicates(songs_list):
    """Basic duplicate detection based on title + artist or exact filename."""
    seen = {}
    duplicates = set()

    for song in songs_list:
        key = (song['title'].strip().lower(), song['artist'].strip().lower())
        if key in seen and song['title'].strip().lower() != 'unknown title':
            duplicates.add(song['filepath'])
            duplicates.add(seen[key])
        else:
            seen[key] = song['filepath']

    return duplicates
