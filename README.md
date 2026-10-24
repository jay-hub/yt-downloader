# yt-downloader
Downloads videos or playlists from Youtube

# Usage
`python playlist-downloader.py <YouTube_URL> [resolution] [type]`

        
#Examples:

##Single video: 
`python playlist-downloader.py https://youtube.com/watch?v=xyz`

##Playlist:
`python playlist-downloader.py https://youtube.com/playlist?list=xyz playlist`
        
##With resolution: 
`python playlist-downloader.py https://youtube.com/watch?v=xyz 720p`

##As tagged MP3s (single song or playlist):
`python playlist-downloader.py <YouTube_URL> mp3 [--to=/music/folder]`

Saves `<folder>/<Artist>/<Title>.mp3` with title, artist, album and cover art tags.
Playlists also get `<folder>/Playlists/<playlist>.m3u`. Videos already downloaded are skipped
(listed in `<folder>/.archive.txt`), so a playlist can be re-run to fetch only new songs.

- Folder: `--to=`, else `$YT_MUSIC_DIR`, else `/srv/music/YouTube` (Pi), else `./downloads/music`
- Names: YouTube's own artist/track info when it has it, otherwise DeepSeek cleans the video title
  (key in `$DEEPSEEK_API_KEY` or `~/.deepseek_key`; without a key the raw title is used)
- Needs `pip install yt-dlp mutagen` and ffmpeg
