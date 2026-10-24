import os
import sys
import yt_dlp

from tagger import TagAndFile


def default_library():
    """
    Where MP3s go: $YT_MUSIC_DIR, else /srv/music/YouTube on the Pi, else ./downloads/music
    """
    if os.environ.get('YT_MUSIC_DIR'):
        return os.environ['YT_MUSIC_DIR']
    if os.path.isdir('/srv/music'):
        return '/srv/music/YouTube'
    return os.path.join(os.getcwd(), 'downloads', 'music')


def download_youtube_audio(url, library=None):
    """
    Download a video or a whole playlist as tagged MP3s, filed as <library>/<Artist>/<Title>.mp3

    Videos already downloaded once (listed in <library>/.archive.txt) are skipped,
    so the same playlist can be run again to pick up only the new songs.

    :param url: YouTube URL (video or playlist)
    :param library: Music folder (optional, see default_library)
    :return: Tuple of (filed MP3 paths, skipped videos)
    """
    library = library or default_library()
    staging = os.path.join(library, '.incoming')
    os.makedirs(staging, exist_ok=True)

    filed = []
    skipped = []

    def note_errors(d):
        if d['status'] == 'error':
            skipped.append(d.get('info_dict', {}).get('title', 'Unknown video'))

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(staging, '%(id)s.%(ext)s'),
        'progress_hooks': [download_progress, note_errors],
        'download_archive': os.path.join(library, '.archive.txt'),
        'writethumbnail': True,
        'postprocessors': [
            {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'},
            {'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg', 'when': 'before_dl'},
            {'key': 'EmbedThumbnail'},
        ],
        'no_color': True,
        'ignoreerrors': True,  # Continue past private/removed videos in a playlist
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # 'after_move': yt-dlp's own MoveFiles step would otherwise move the file back into staging
        ydl.add_post_processor(TagAndFile(library, filed), when='after_move')
        ydl.download([url])

    print(f"\nBoom ! {len(filed)} new song(s) filed in {library}")
    if skipped:
        print(f"Skipped (private or error): {len(skipped)}")
        for title in set(skipped):
            print(f"  - {title}")
    return filed, skipped


def download_youtube_content(url, output_path=None, resolution=None, download_type='video'):
    """
    Download YouTube video or playlist with improved error handling for private videos

    :param url: YouTube URL (video or playlist)
    :param output_path: Directory to save the content (optional)
    :param resolution: Specific resolution to download (optional)
    :param download_type: 'video' or 'playlist'
    :return: Tuple of (downloaded files, skipped files)
    """
    try:
        if output_path is None:
            output_path = os.path.join(os.getcwd(), 'downloads')
        os.makedirs(output_path, exist_ok=True)

        ydl_opts = {
            'format': 'best[ext=mp4]',
            'outtmpl': os.path.join(output_path,
                                    '%(playlist_title|)s/%(title)s.%(ext)s'
                                    if download_type == 'playlist'
                                    else '%(title)s.%(ext)s'
                                    ),
            'progress_hooks': [download_progress],
            'nooverwrites': True,
            'no_color': True,
            'ignoreerrors': True, # Important: Continue on error
            'no_warnings': True,
        }

        if resolution:
            ydl_opts['format'] = f'best[height<={resolution[:-1]}][ext=mp4]'

        downloaded_files = []
        skipped_files = []  # to handle private videos in playlists

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info_dict = ydl.extract_info(url, download=True)

                if download_type == 'playlist':
                    if 'entries' in info_dict:
                        for entry in info_dict['entries']:
                            if not entry:
                                print(f"Skipping unavailable video in playlist")
                                skipped_files.append('Unavailable Video')
                                continue

                            try:
                                # Check if video is not private
                                if entry.get('availability') == 'private':
                                    print(f"Skipping private video: {entry.get('title', 'Private Video Title')}")
                                    skipped_files.append(entry.get('title', 'Private Video'))
                                    continue

                                filename = ydl.prepare_filename(entry)
                                if os.path.exists(filename):
                                    downloaded_files.append(filename)
                                else:
                                    print(f"Could not download: {entry.get('title', 'Something off with this Video')}")
                                    skipped_files.append(entry.get('title', 'Something off with this Video'))
                            except Exception as err:
                                print(f"Error processing playlist entry: {err}")
                                skipped_files.append('Error Processing Video')
                else:
                    # For single video
                    # Check if the video is private
                    if info_dict.get('availability') == 'private':
                        print(f"Cannot download private video: {info_dict.get('title', 'Private Video Title')}")
                        skipped_files.append(info_dict.get('title', 'Private Video Title'))
                    else:
                        filename = ydl.prepare_filename(info_dict)
                        if os.path.exists(filename):
                            downloaded_files.append(filename)
                        else:
                            print(f"Could not download: {info_dict.get('title', 'Something off with this Video')}")
                            skipped_files.append(info_dict.get('title', 'Something off with this Video'))

            except Exception as err:
                print(f"Unexpected error during download: {err}")
                return [], [f"Unexpected Error: {err}"]

            # Print summary
            print(f"\nBoom ! Download complete.")
            print(f"Total downloaded files: {len(downloaded_files)}")
            if skipped_files:
                print(f"Skipped files (private or error): {len(skipped_files)}")
                print("Skipped file details:")
                for skipped in set(skipped_files):
                    print(f"  - {skipped}")

            return downloaded_files, skipped_files

    except Exception as e:
        print(f"Download failed: {e}")
        return [], [str(e)]


def download_progress(d):
    """
    Callback function to show download progress
    """
    if d['status'] == 'downloading':
        downloaded_bytes = d.get('downloaded_bytes', 0)
        total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
        if total_bytes > 0:
            percent = downloaded_bytes * 100 / total_bytes
            print(f"\rDownloading: {percent:.1f}%", end='', flush=True)


def main():
    print('Starting YouTube Downloader')
    # Check if URL is provided as an argument
    if len(sys.argv) < 2:
        print("Usage: python playlist-downloader.py <YouTube_URL> [resolution] [type]")
        print("Examples:")
        print("  Single video: python playlist-downloader.py https://youtube.com/watch?v=xyz")
        print("  Playlist: python playlist-downloader.py https://youtube.com/playlist?list=xyz playlist")
        print("  With resolution: python playlist-downloader.py https://youtube.com/watch?v=xyz 720p")
        print("  As tagged MP3s (song or playlist): python playlist-downloader.py <YouTube_URL> mp3 [--to=/music/folder]")
        sys.exit(1)

    video_url = sys.argv[1]

    resolution = None
    download_type = 'video'
    audio = False
    library = None

    for arg in sys.argv[2:]:
        if arg.lower() == 'mp3':
            audio = True
        elif arg.startswith('--to='):
            library = arg[len('--to='):]
        elif arg.endswith('p'):
            resolution = arg
        elif arg.lower() == 'playlist':
            download_type = 'playlist'

    if audio:
        download_youtube_audio(video_url, library)
        return

    downloaded_files, skipped_files = download_youtube_content(
        video_url,
        resolution=resolution,
        download_type=download_type
    )

    if downloaded_files:
        print("\nSuccessfully Downloaded Files:")
        for file in downloaded_files:
            print(f"  - {file}")


if __name__ == "__main__":
    main()
