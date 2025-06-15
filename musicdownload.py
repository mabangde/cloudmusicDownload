import os
import inspect
from pycloudmusic import LoginMusic163, Music163Api
from pathlib import Path
from mutagen.flac import FLAC, Picture
from mutagen.mp3 import MP3
from mutagen.easymp4 import EasyMP4
from mutagen.id3 import TIT2, TPE1, TALB, APIC
from mutagen.mp4 import MP4Cover
import asyncio
import qrcode
import requests




COOKIE_FILE = "cookie.txt"
BASE_DOWNLOAD_DIR = "./download"

PLAYLIST_IDS = [13743018730]
SONG_IDS = []
QUALITY = "mp3"

def safe_filename(s):
    safe_chars = " -_.()[]{}'!@#$%^&+=`~"
    return "".join(c if c.isalnum() or c in safe_chars else "_" for c in s).strip()

def get_first_str(val):
    if isinstance(val, list):
        return next((str(x) for x in val if str(x).strip()), "unknown")
    return str(val) if val else "unknown"

def get_real_ext(filepath):
    try:
        with open(filepath, "rb") as f:
            header = f.read(16)
        if header.startswith(b'fLaC'):
            return '.flac'
        elif header.startswith(b'ID3') or header[:2] == b'\xFF\xFB':
            return '.mp3'
        elif header.startswith(b'RIFF'):
            return '.wav'
        elif b'M4A' in header or b'isom' in header or b'ftyp' in header:
            return '.m4a'
        else:
            return Path(filepath).suffix
    except Exception:
        return None

def write_tags(filepath, ext, title, artist, album):
    try:
        if ext == '.flac':
            audio = FLAC(filepath)
            audio['title'] = title
            audio['artist'] = artist
            audio['album'] = album
            audio.save()
        elif ext == '.mp3':
            audio = MP3(filepath)
            if audio.tags is None:
                audio.add_tags()
            audio.tags.add(TIT2(encoding=3, text=title))
            audio.tags.add(TPE1(encoding=3, text=artist))
            audio.tags.add(TALB(encoding=3, text=album))
            audio.save()
        elif ext == '.m4a':
            audio = EasyMP4(filepath)
            audio['title'] = title
            audio['artist'] = artist
            audio['album'] = album
            audio.save()
    except Exception:
        pass

def download_cover(url):
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.content
    except Exception:
        pass
    return None

def write_cover(filepath, ext, cover_data):
    try:
        if not cover_data:
            return
        if ext == '.flac':
            audio = FLAC(filepath)
            pic = Picture()
            pic.data = cover_data
            pic.type = 3
            pic.mime = "image/jpeg"
            audio.clear_pictures()
            audio.add_picture(pic)
            audio.save()
        elif ext == '.mp3':
            audio = MP3(filepath)
            if audio.tags is None:
                audio.add_tags()
            audio.tags.version = (2, 3, 0)
            audio.tags.add(
                APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,
                    desc="Cover",
                    data=cover_data
                )
            )
            audio.save(v2_version=3)
        elif ext == '.m4a':
            from mutagen.mp4 import MP4, MP4Cover
            audio = MP4(filepath)
            audio["covr"] = [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
            audio.save()
    except Exception:
        pass

async def process_music(music, playlist_dir, write_lyric=True):
    try:
        if QUALITY == "mp3":
            await music.play(br=320000)
        elif QUALITY == "flac":
            await music.play(br=999000)
        else:
            await music.play()
    except Exception as e:
        print(f"[FAIL] {get_first_str(getattr(music, 'name', None))}: {e}")
        return

    music_id = str(getattr(music, "id", None))
    src_path = None
    for ext in [".mp3", ".flac", ".m4a", ".wav"]:
        candidate = os.path.join(BASE_DOWNLOAD_DIR, f"{music_id}{ext}")
        if os.path.exists(candidate):
            src_path = candidate
            break
    if not src_path:
        print(f"[FAIL] Not found: {music_id}")
        return

    artist = get_first_str(getattr(music, "artist_str", None))
    album = get_first_str(getattr(music, "album_str", None))
    title = get_first_str(getattr(music, "name", None))
    real_ext = get_real_ext(src_path)
    if not real_ext:
        print(f"[FAIL] Skip unrecognized file: {src_path}")
        return
    final_name = safe_filename(f"{artist} - {album} - {title}{real_ext}")
    final_path = os.path.join(playlist_dir, final_name)
    if os.path.exists(final_path):
        print(f"[SKIP] Already exists: {final_name}")
        return
    try:
        os.makedirs(playlist_dir, exist_ok=True)
        os.rename(src_path, final_path)
        write_tags(final_path, real_ext, title, artist, album)
        # Cover
        cover_url = getattr(music, "album_pic_url", None) or getattr(music, "cover_url", None)
        if not cover_url and hasattr(music, "album_data"):
            album_data = getattr(music, "album_data")
            if isinstance(album_data, dict):
                cover_url = album_data.get("picUrl")
        if cover_url:
            cover_data = download_cover(cover_url)
            write_cover(final_path, real_ext, cover_data)
        # Lyric
        if write_lyric and hasattr(music, "lyric"):
            try:
                lyric = None
                if callable(music.lyric):
                    result = music.lyric()
                    if inspect.isawaitable(result):
                        lyric = await result
                    else:
                        lyric = result
                else:
                    lyric = music.lyric
                if isinstance(lyric, dict):
                    if "lrc" in lyric and isinstance(lyric["lrc"], dict) and "lyric" in lyric["lrc"]:
                        lyric = lyric["lrc"]["lyric"]
                    elif "lyric" in lyric:
                        lyric = lyric["lyric"]
                    elif "lrc" in lyric:
                        lyric = lyric["lrc"]
                    elif "tlyric" in lyric and isinstance(lyric["tlyric"], dict) and "lyric" in lyric["tlyric"]:
                        lyric = lyric["tlyric"]["lyric"]
                    else:
                        lyric = ""
                if isinstance(lyric, str) and lyric.strip():
                    lrc_path = os.path.splitext(final_path)[0] + ".lrc"
                    with open(lrc_path, "w", encoding="utf-8") as f:
                        f.write(lyric)
                    print(f"[OK] Lyric: {os.path.basename(lrc_path)}")
            except Exception:
                pass
        print(f"[OK] {final_name}")
    except Exception as e:
        print(f"[FAIL] {final_name}: {e}")

async def main():
    musicapi = None
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            cookie = f.read().strip()
        musicapi = Music163Api(cookie)
        try:
            await musicapi.my()
            print("Cookie login success.")
        except Exception:
            print("Cookie expired, need QR login.")
            musicapi = None

    if musicapi is None:
        login = LoginMusic163()
        qr_key, qr_url = await login.qr_key()
        qr = qrcode.QRCode()
        qr.add_data(qr_url)
        print("Scan QR code with NetEase Cloud Music App:")
        qr.print_ascii(invert=True)
        cookie, musicapi = await login.qr(qr_key)
        print("QR login success.")
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            f.write(cookie)
        print("Cookie saved.")
        print(await musicapi.my())

    if not PLAYLIST_IDS and not SONG_IDS:
        print("No playlist or song ID specified. Exit.")
        return

    for playlist_id in PLAYLIST_IDS:
        playlist = await musicapi.playlist(playlist_id)
        playlist_list = list(playlist)
        playlist_name = safe_filename(get_first_str(getattr(playlist, "name", None)))
        playlist_dir = os.path.join(BASE_DOWNLOAD_DIR, playlist_name)
        print(f"\n=== Playlist: {playlist_name} (ID: {playlist_id}) ===")
        print(f"Total tracks: {len(playlist_list)}")
        tasks = [process_music(music, playlist_dir, write_lyric=True) for music in playlist_list]
        await asyncio.gather(*tasks)

    if SONG_IDS:
        single_dir = os.path.join(BASE_DOWNLOAD_DIR, "Single")
        os.makedirs(single_dir, exist_ok=True)
        print(f"\n=== Single Download ===")
        tasks = []
        for song_id in SONG_IDS:
            try:
                music = await musicapi.song(song_id)
                tasks.append(process_music(music, single_dir, write_lyric=True))
            except Exception as e:
                print(f"[FAIL] Single {song_id}: {e}")
        if tasks:
            await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
