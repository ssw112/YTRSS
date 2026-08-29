"""Playlist polling via yt-dlp (zero-auth: unlisted playlist, no cookies)."""
import subprocess

YT_DLP = "yt-dlp"  # on PATH inside the container


def fetch_playlist_ids(playlist_url):
    cmd = [YT_DLP, "--flat-playlist", "--get-id", playlist_url]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if res.returncode != 0:
        raise RuntimeError(f"yt-dlp playlist fetch failed: {res.stderr.strip()[:300]}")
    return [line.strip() for line in res.stdout.splitlines() if line.strip()]
