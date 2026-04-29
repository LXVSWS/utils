import os
import sys
import subprocess
import json
import re

def main():
    if len(sys.argv) < 2:
        print("Provide a BC URL as argument")
        return
    elif len(sys.argv) < 3:
        extension = "mp3"
    else:
        extension = sys.argv[2]

    print("🔥 BCDL")
    url = sys.argv[1]
    album_name, track_names = extract_album_name(url)
    print(f"📀 {album_name}")
    downloaded_files = download_files(url, album_name)
    rename_files(album_name, downloaded_files, track_names, extension)
    download_cover(url, album_name)
    print("😈 Enjoy")

def extract_album_name(url):
    curl_cmd = f'curl -sS {url} | sed -n \'/<script type="application\\/ld+json">/,/<\\/script>/ {{/<script type="application\\/ld+json">/d; /<\\/script>/d; p;}}\''

    try:
        result = subprocess.check_output(curl_cmd, shell=True, text=True)
        json_data = json.loads(result.strip())
        album_name = json_data.get('name', 'Unknown Album')
        album_name = sanitize_filename(album_name)
        track_names = extract_track_names(json_data)
        return album_name, track_names
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        return 'Unknown Album', []
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return 'Unknown Album', []

def extract_track_names(json_data):
    track_names = []
    if 'track' in json_data and 'itemListElement' in json_data['track']:
        for item in json_data['track']['itemListElement']:
            track_info = item.get('item', {})
            track_name = track_info.get('name')
            if track_name:
                track_names.append(track_name)
    return track_names

def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]+', '_', filename)

def download_files(url, album_name):
    print("💻 Downloading files...")
    os.makedirs(album_name, exist_ok=True)
    curl_cmd = f'curl -sS {url} | grep -o "https://t4.bcbits.com/stream/[^}}]*"'

    try:
        result = subprocess.check_output(curl_cmd, shell=True, text=True)
        file_urls = result.strip().split('\n')

        downloaded_files = []
        for file_url in file_urls:
            sanitized_name = sanitize_filename(file_url.split("/")[-1])
            filename = os.path.join(album_name, sanitized_name)
            subprocess.check_call(f'curl -sS -o "{filename}" "{file_url}"', shell=True)
            downloaded_files.append(filename)

        print(f"✅ Files downloaded")
        return downloaded_files
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        return []

def download_cover(url, album_name):
    print("💻 Downloading cover...")

    curl_cmd = f'curl -sS {url} | grep -o \'<meta[^>]*property="og:image"[^>]*content="[^"]*"\' | sed \'s/.*content="\\([^"]*\\)".*/\\1/\' | xargs -I{{}} curl -sS {{}} -o "{album_name}/cover.jpg"'

    try:
        subprocess.check_call(curl_cmd, shell=True)
        print("✅ Cover downloaded")
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")

def rename_files(album_name, downloaded_files, track_names, extension):
    print("💻 Renaming files...")
    try:
        for i, old_path in enumerate(downloaded_files):
            track_name = f"{i + 1} - {track_names[i]}" if i < len(track_names) else f"track_{i + 1}"
            new_path = os.path.join(album_name, f"{track_name}.{extension}")
            os.rename(old_path, new_path)
        print("✅ Files renamed")
    except OSError as e:
        print(f"Error renaming files: {e}")

if __name__ == "__main__":
    main()
