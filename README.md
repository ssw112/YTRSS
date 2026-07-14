# 🎥 YouTube-to-RSS AI Summarizer

A lightweight, self-hosted utility that automatically turns YouTube videos from a playlist into beautifully formatted, publication-ready text articles inside your favorite RSS reader (Feedly, NetNewsWire, etc.).

---

## ✨ Features

- **🔑 Zero YouTube API Keys Required**: Bypasses the complex Google Cloud / OAuth setup. Simply put videos into a public or unlisted YouTube playlist, and the script reads the queue automatically!
- **💸 Unbelievably Cheap**: Powered by **Gemini 2.5 Flash-Lite** (via LiteLLM). Summarizing a 1-hour podcast costs **less than 1/10th of a cent**.
- **📖 Inline Feedly/RSS Reading**: Automatically maps RSS link headers to custom dummy links, forcing Feedly to render your summaries natively inline instead of redirecting you directly to the YouTube app.
- **⚡ Sentient AI Prompting**: Dynamically structures output based on the content archetype (e.g., action-oriented checklists for tutorials, speaker-by-speaker debates for podcasts, conceptual breakdowns for lectures).
- **🗣️ Multi-lingual**: Summarizes in the spoken native language (Ukrainian, Russian, Spanish, English) or auto-translates any other language to English.

---

## 🛠️ How it Works

```
[ You queue video in YT Playlist ]
               │
               ▼
[ sync_playlist.py runs via Cron ]
               │
               ▼
   [ Downloads auto-subtitles ] (using yt-dlp)
               │
               ▼
    [ Cleans ASR repetition ]   (using srt_cleaner.py)
               │
               ▼
[ Synthesizes deep text article ] (using Gemini 2.5 via LiteLLM)
               │
               ▼
 [ Appends to local feed.xml ]  (using rss_builder.py)
```

---

## 🚀 Quick Start (Self-Hosted)

### 1. Prerequisites
Ensure you have `Python 3.9+` and `yt-dlp` installed:
```bash
# On macOS (using Homebrew)
brew install yt-dlp ffmpeg

# On Debian/Ubuntu
sudo apt install yt-dlp ffmpeg
```

### 2. Installation
Clone this repository and install dependencies:
```bash
git clone https://github.com/your-username/yt-rss-summarizer.git
cd yt-rss-summarizer
pip3 install -r requirements.txt
```

### 3. Configuration
Copy the `.env.example` file to `.env` and configure your settings:
```bash
cp .env.example .env
```

Open `.env` and fill in:
- **`PLAYLIST_URL`**: Your public or unlisted YouTube playlist URL.
- **Your LLM credentials** (e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GOOGLE_APPLICATION_CREDENTIALS` path).

### 4. Running the Sync
Run the sync script to pull new videos, summarize them, and build the RSS feed:
```bash
python3 sync_playlist.py
```

It will create a local `feed.xml` file.

### 5. Automate with Cron
To run this hourly in the background on your Mac/Server, open your crontab:
```bash
crontab -e
```

And append an hourly execution (adjust paths to your system):
```cron
0 * * * * cd /path/to/yt-rss-summarizer && python3 sync_playlist.py >> sync.log 2>&1
```

---

## 📰 Serving to Feedly / RSS Clients

Because `feed.xml` is a static file, you can serve it easily:
1. **Local LAN**: Run a basic Python server in the project directory:
   ```bash
   python3 -m http.server 8090
   ```
   Add `http://<your-local-ip>:8090/feed.xml` directly to your RSS reader!
2. **WAN / Remote Access**: Point a lightweight reverse proxy like Caddy or Nginx at the file, or deploy it to a static hosting directory.

---

## 📜 License
MIT License. Feel free to use, modify, and distribute!
