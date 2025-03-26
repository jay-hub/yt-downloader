import os
import sys
import yt_dlp


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
        sys.exit(1)

    video_url = sys.argv[1]

    resolution = None
    download_type = 'video'

    for arg in sys.argv[2:]:
        if arg.endswith('p'):
            resolution = arg
        elif arg.lower() == 'playlist':
            download_type = 'playlist'

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
