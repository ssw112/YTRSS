import os
import json
import subprocess
from dotenv import load_dotenv
from summarize_yt import process_youtube_video

# Load local environment variables from .env file
load_dotenv()

PROCESSED_PATH = os.environ.get("PROCESSED_VIDEOS_PATH", "processed_videos.json")
YT_DLP_PATH = os.environ.get("YT_DLP_PATH", "yt-dlp")
PLAYLIST_URL = os.environ.get("PLAYLIST_URL", "https://www.youtube.com/playlist?list=PLcE_sBNWz5YQ")

def load_processed_ids():
    """Loads the list of already processed video IDs."""
    if os.path.exists(PROCESSED_PATH):
        try:
            with open(PROCESSED_PATH, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_processed_ids(processed_set):
    """Saves the updated list of processed video IDs."""
    os.makedirs(os.path.dirname(PROCESSED_PATH) if os.path.dirname(PROCESSED_PATH) else ".", exist_ok=True)
    with open(PROCESSED_PATH, "w") as f:
        json.dump(list(processed_set), f, indent=2)

def fetch_playlist_ids():
    """Fetches all video IDs from the configured unlisted/public playlist."""
    print("Fetching active video IDs from custom RSS playlist...")
    cmd = [
        YT_DLP_PATH,
        "--flat-playlist",
        "--get-id",
        PLAYLIST_URL
    ]
    
    env = os.environ.copy()
    env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + env.get("PATH", "")
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, env=env, check=True)
        # Split output lines and filter empty values
        video_ids = [line.strip() for line in res.stdout.split("\n") if line.strip()]
        return video_ids
    except Exception as e:
        print(f"Failed to fetch playlist IDs: {e}")
        return []

def run_sync():
    """Compares Watch Later playlist against processed list and runs summarization for any new videos."""
    processed_ids = load_processed_ids()
    playlist_ids = fetch_playlist_ids()
    
    if not playlist_ids:
        print("No videos found in playlist or failed to read playlist.")
        return
        
    # We find the intersection of what is in the playlist but not processed yet
    new_ids = [vid for vid in playlist_ids if vid not in processed_ids]
    
    print(f"Total videos in playlist: {len(playlist_ids)}")
    print(f"Already processed videos: {len(processed_ids)}")
    print(f"New videos to process: {len(new_ids)}")
    
    if not new_ids:
        print("Everything is up to date. No new videos to summarize.")
        return
        
    # Loop through new videos until one successfully processes!
    processed_any = False
    for target_id in new_ids:
        print(f"\n🚀 Attempting video ID: {target_id}")
        url = f"https://www.youtube.com/watch?v={target_id}"
        success = process_youtube_video(url)
        
        if success:
            processed_ids.add(target_id)
            save_processed_ids(processed_ids)
            print(f"Successfully processed and marked {target_id} as read!")
            processed_any = True
            break  # Stop after processing 1 successful video to save resources/rates
        else:
            print(f"Skipping {target_id} (no captions or failed). Marking as processed to keep the queue moving.")
            processed_ids.add(target_id)
            save_processed_ids(processed_ids)
            
    if not processed_any:
        print("\nAll new videos in queue were skipped (no captions or failed).")

if __name__ == "__main__":
    run_sync()
