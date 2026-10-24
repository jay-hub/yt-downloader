import json
import os
import re
import urllib.request

import yt_dlp
from mutagen.id3 import ID3, ID3NoHeaderError, TIT2, TPE1, TALB, TPE2, TDRC, COMM, TXXX

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

PROMPT = """Extract the song info from this YouTube video. Return json:
{"artist": str, "title": str, "album": str, "year": str}
- artist: main singer or band only (not the channel, label or "ft." guests unless they are the main artist)
- title: the song name only. Drop "Official Video", "Lyrics", "HD", "4K", channel handles and emoji.
  For bilingual titles (e.g. Sinhala | English) use the romanised/English form.
- album: only if the title or description names an album, film, show or series (e.g. "Coke RED"), else ""
- year: only if stated, else ""
Never invent an artist: if unsure, use the channel name."""


def deepseek_key():
    """
    Read the DeepSeek API key from $DEEPSEEK_API_KEY or ~/.deepseek_key
    """
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        path = os.path.expanduser("~/.deepseek_key")
        if os.path.exists(path):
            with open(path) as f:
                key = f.read().strip()
    return key


def ask_deepseek(info):
    """
    Ask DeepSeek to clean up a YouTube title into artist / title / album

    :param info: yt-dlp info dict for one video
    :return: dict with artist, title, album, year (or None if no key or the call failed)
    """
    key = deepseek_key()
    if not key:
        return None
    video = (f"Title: {info.get('title', '')}\n"
             f"Channel: {info.get('channel') or info.get('uploader', '')}\n"
             f"Description: {(info.get('description') or '')[:600]}")
    body = json.dumps({
        "model": DEEPSEEK_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": video}],
    }).encode()
    request = urllib.request.Request(DEEPSEEK_URL, body, {"Authorization": f"Bearer {key}",
                                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            reply = json.load(response)
        return json.loads(reply["choices"][0]["message"]["content"])
    except Exception as err:
        print(f"\nDeepSeek lookup failed, using the YouTube title: {err}")
        return None


def song_info(info):
    """
    Work out artist / title / album for one video.
    YouTube's own music metadata wins when present, then DeepSeek, then the raw title.
    """
    if info.get("track") and (info.get("artist") or info.get("creator")):
        artist = (info.get("artist") or info.get("creator")).split(",")[0].strip()
        return {"artist": artist, "title": info["track"], "album": info.get("album") or "",
                "year": str(info.get("release_year") or ""), "source": "youtube"}
    cleaned = ask_deepseek(info)
    if cleaned and cleaned.get("title"):
        return {**cleaned, "source": "deepseek"}
    return {"artist": info.get("channel") or info.get("uploader") or "Unknown Artist",
            "title": info.get("title", "Unknown"), "album": "", "year": "", "source": "raw"}


def safe_name(text):
    """
    Make a string safe to use as a file or folder name
    """
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", text)
    return re.sub(r"\s+", " ", text).strip(" .")[:120] or "Unknown"


def write_tags(path, song, info):
    """
    Write ID3 tags, keeping the cover art yt-dlp already embedded
    """
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    tags.setall("TIT2", [TIT2(encoding=3, text=song["title"])])
    tags.setall("TPE1", [TPE1(encoding=3, text=song["artist"])])
    tags.setall("TPE2", [TPE2(encoding=3, text=song["artist"])])
    # A single with no album: use the title as the album, so Navidrome doesn't lump them into "Unknown Album"
    tags.setall("TALB", [TALB(encoding=3, text=song.get("album") or song["title"])])
    if song.get("year"):
        tags.setall("TDRC", [TDRC(encoding=3, text=song["year"])])
    url = info.get("webpage_url") or f"https://www.youtube.com/watch?v={info.get('id')}"
    tags.setall("COMM", [COMM(encoding=3, lang="eng", desc="", text=url)])
    tags.setall("TXXX:youtube_id", [TXXX(encoding=3, desc="youtube_id", text=info.get("id", ""))])
    tags.save(path, v2_version=3)


def add_to_playlist(library, playlist_title, song_path):
    """
    Append a song to <library>/Playlists/<playlist>.m3u (Navidrome imports these)
    """
    folder = os.path.join(library, "Playlists")
    os.makedirs(folder, exist_ok=True)
    m3u = os.path.join(folder, safe_name(playlist_title) + ".m3u")
    entry = os.path.relpath(song_path, folder)
    lines = []
    if os.path.exists(m3u):
        with open(m3u, encoding="utf-8") as f:
            lines = f.read().splitlines()
    if entry not in lines:
        with open(m3u, "a", encoding="utf-8") as f:
            if not lines:
                f.write("#EXTM3U\n")
            f.write(entry + "\n")


class TagAndFile(yt_dlp.postprocessor.PostProcessor):
    """
    Runs after the MP3 conversion: tags the file and moves it to <library>/<Artist>/<Title>.mp3
    """

    def __init__(self, library, filed):
        super().__init__()
        self.library = library
        self.filed = filed  # list collecting the final paths, for the summary

    def run(self, info):
        source = info["filepath"]
        song = song_info(info)
        write_tags(source, song, info)

        folder = os.path.join(self.library, safe_name(song["artist"]))
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, safe_name(song["title"]) + ".mp3")
        n = 2
        while os.path.exists(target):
            target = os.path.join(folder, f"{safe_name(song['title'])} ({n}).mp3")
            n += 1
        os.replace(source, target)
        info["filepath"] = target

        if info.get("playlist_title"):
            add_to_playlist(self.library, info["playlist_title"], target)
        print(f"\nFiled ({song['source']}): {song['artist']} - {song['title']}  ->  {target}")
        self.filed.append(target)
        return [], info
