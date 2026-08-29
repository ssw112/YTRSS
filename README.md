# ytfeed

YouTube playlist → AI summary → RSS feed you can read in Feedly (or any RSS reader).

Videos you add to a dedicated **unlisted YouTube playlist** are detected automatically,
transcribed from their auto-captions (in the video's *original* language), summarized
into a styled HTML article by an LLM, and appended to an RSS feed. Each feed item links
to a built-in article page — never directly to youtube.com, so Feedly renders the text
instead of bouncing you to the YouTube app.

## Quickstart

```bash
git clone <this repo> && cd ytfeed
cp .env.example .env          # fill in your LLM API key(s) + a random setup token
cp config.example.yml data/config.yml   # edit: playlist URL, providers, public_base_url
docker compose up -d --build
```

Then check `http://<host>:8091/status` — it shows the exact feed URL to import into
your RSS reader, the last sync result, and per-provider health.

### Endpoints

| Path | What it does |
|---|---|
| `/feed.xml` | The RSS feed (import this into your reader) |
| `/article/{video_id}` | Rendered article page (what feed links point to) |
| `/status` | Feed URL, last run, last published article, provider health |
| `/setup?token=…` | Edit config.yml in the browser (token from `.env`) |
| `POST /test-provider?token=…` | Live one-token completion test of each provider |
| `/healthz` | Liveness probe (used by the Docker healthcheck) |

## Configuration notes

- **Playlist**: create a new *unlisted* playlist and add videos to it (don't use the real
  Watch Later — it needs cookies that expire; unlisted playlists are fetchable with zero auth).
- **LLM providers** are an ordered fallback chain. Never trust a ":free" model label —
  many reject with "insufficient credit". `POST /test-provider` runs the only valid test:
  a real completion.
- **Language**: the original spoken language is detected from YouTube's `*-orig` caption
  track and hard-locked in the prompt; output is verified with langdetect and retried or
  escalated on mismatch. Configure kept-vs-translated languages in `ytfeed/summarize.py`
  (`KEEP_LANGS`).
- **Prompt**: `prompts/summarize.md` is a plain editable file (placeholders: `{title}`,
  `{video_id}`, `{language_rule}`, `{transcript}`).
- Feed is capped at `feed.max_items` (default 20). All state lives in `./data/`
  (config.yml, feed.xml, processed_videos.json, state.json) — back up = copy that folder.

## Making the feed public (Feedly needs HTTPS on port 443)

Feedly rejects feed URLs on non-standard ports, so the container must be reachable at
`https://your.domain/feed.xml` with a valid certificate. The standard setup:

### 1. Dynamic DNS
Give your home IP a hostname (most routers have built-in DDNS: TP-Link → tplinkdns.com,
or use DuckDNS/Cloudflare). Set that hostname as `feed.public_base_url` in config.yml.

### 2. Reverse proxy (Caddy)
Caddy gets and renews the TLS certificate automatically. Minimal Caddyfile:

```
your.domain.example:8443 {
    reverse_proxy localhost:8091
}
```

(Any internal HTTPS port works — the router maps public 443 onto it in the next step.
If Caddy also serves other sites, add this as one more site block.)

### 3. Router port-forward
Forward **WAN TCP 443 → LAN <docker-host-ip>:8443** (the Caddy port above).
Do NOT forward 8091 directly — that would expose plain HTTP.

Result: `https://your.domain.example/feed.xml` works from anywhere; that's the URL
you paste into Feedly. Article links inside the feed use the same domain automatically
(they're built from `public_base_url`).

### Security
- `/setup` and `/test-provider` are token-protected (`YTFEED_SETUP_TOKEN` in `.env`) —
  they share the public domain with the feed, and an unauthenticated setup page would
  let anyone rewrite your config and read your keys.
- API keys belong in `.env` (referenced from config.yml as `${VARS}`), never in config.yml.

## Operations

- Logs: `docker logs -f ytfeed` (every sync, every provider failure — no silent errors).
- The scheduler is an internal loop (`playlist.poll_interval_seconds`, default hourly).
  Stopping the container just freezes the feed; readers tolerate that and it resumes on start.
- A video is blacklisted (never retried) **only** when it has no usable captions.
  LLM/API failures are retried next cycle — a provider outage can't silently eat videos.
- **yt-dlp is pinned** in `requirements.txt`. YouTube breaks it regularly: if `/status`
  shows playlist or subtitle errors, bump the pin to the latest release and
  `docker compose up -d --build`.

## License

MIT
