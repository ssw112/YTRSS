# ytfeed

Version 2.1 (see [Changelog](#changelog)).

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
| `/feed.xml` | The RSS feed of the main playlist (import this into your reader) |
| `/article/{video_id}` | Rendered article page (what feed links point to) |
| `/{name}.xml`, `/{name}/{video_id}` | Same two, for each extra source (see Multiple sources) |
| `/status` | Feed URL, last run, last published article, provider health |
| `/setup?token=…` | Edit config.yml in the browser (token from `.env`) |
| `POST /test-provider?token=…` | Live one-token completion test of each provider |
| `/healthz` | Liveness probe (used by the Docker healthcheck) |

## Configuration notes

- **Playlist**: create a new *unlisted* playlist and add videos to it (don't use the real
  Watch Later — it needs cookies that expire; unlisted playlists are fetchable with zero auth).
- **LLM providers** are an ordered fallback chain of OpenAI-compatible endpoints (see
  LLM endpoint below). Never trust a ":free" model label —
  many reject with "insufficient credit". `POST /test-provider` runs the only valid test:
  a real completion.
- **Language**: the original spoken language is detected from YouTube's `*-orig` caption
  track and hard-locked in the prompt; output is verified with langdetect and retried or
  escalated on mismatch. Configure kept-vs-translated languages in `ytfeed/summarize.py`
  (`KEEP_LANGS`).
- **Prompt**: `prompts/summarize.md` is a plain editable file (placeholders: `{title}`,
  `{video_id}`, `{language_rule}`, `{transcript}`).
- Feed is capped at `feed.max_items` (default 20; see Feed caps). All state lives in
  `./data/` (config.yml, feeds, ledgers, articles/, state.json) — back up = copy that folder.

## Multiple sources

The top-level `playlist:` block is the implicit source `main`. Add more playlists under
`sources:`, each with its own feed. Only `name` and `url` are required; the rest is derived
from the name (override any of it per source):

| Setting | Derived default for source `foo` |
|---|---|
| Feed file | `foo.xml` (`feed.xml` for main) |
| Ledger | `processed_foo.json` (`processed_videos.json` for main) |
| Archive dir | `articles/foo/` (`articles/` for main) |
| Route | `/foo/{video_id}` for article pages (`/article/{id}` for main) |
| Prompt | `/app/prompts/foo.md` (`llm.prompt_path` for main) |
| Poll interval | 600 s (main: `playlist.poll_interval_seconds`) |
| Max items | `feed.max_items` |

`feed_title`, `feed_description` and `title_prefix` are also per source. One scheduler loop
runs every source on its own clock. `main`, `article` and `feed` are reserved names.
`prompts/tldr.md` is a second example prompt (short TLDR plus a verification pass).
See `config.example.yml`.

## LLM endpoint

Each entry in `llm.providers` needs `label`, `model`, `api_base` and `api_key`. Anything that
speaks the OpenAI chat-completions API works:

- a local gateway such as LiteLLM (`api_base: http://host.docker.internal:4000/v1` from inside
  Docker Desktop; model is an alias defined in the gateway, which can do its own fallback),
- or a provider directly (`api_base: https://api.provider.example/v1`).

Entries are tried in order. Keys stay in `.env` and are referenced as `${VAR}`.

## Feed caps and rebuilding a feed

Each feed keeps the newest `max_items` entries (per source, falling back to `feed.max_items`).
Older items drop out of the XML but stay in `articles/`, and their article links keep working.

If you raise the cap, or a feed file got damaged or lost items, rebuild it from the archive:

```bash
python3 tools/rebuild_feed.py main --dry-run    # or a source name; --config PATH if not ./data/config.yml
python3 tools/rebuild_feed.py main
```

It takes the newest `max_items` archived articles (by file mtime), keeps guids and dates of
items already in the feed (so readers see no duplicates), writes the file atomically and
needs only PyYAML, no API keys. It overwrites the feed file, so copy it first
(`cp data/feed.xml data/feed.xml.bak`). Stop the container, or run it between syncs, to avoid a
write racing the scheduler.

## Making the feed public (Feedly needs HTTPS on port 443)

Feedly rejects feed URLs on non-standard ports, so the container must be reachable at
`https://your.domain/feed.xml` with a valid certificate. The standard setup:

### 1. Dynamic DNS
Give your home IP a hostname (most routers have built-in DDNS,
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

## Reader cannot reach your host over HTTPS

Some readers (Feedly included) refuse a feed behind a self-signed or internal-CA certificate.
Instead of fixing that, mirror the feed files to a GitHub Pages repo and subscribe to the
Pages URL (`https://<user>.github.io/<repo>/feed.xml`). Article links inside the feed still
point at `public_base_url`, so they open only where that host is reachable.

1. Create a public repo with Pages enabled (branch `main`, root), clone it locally and set
   a git identity inside the clone.
2. Edit the variables at the top of `tools/publish_pages.sh` (feed dir, file names, clone path).
   It copies the files in, then commits and pushes only if something changed.
3. Run it on a timer.

cron:

```
*/15 * * * * /path/to/ytfeed/tools/publish_pages.sh
```

launchd (`~/Library/LaunchAgents/com.example.ytfeed-pages.plist`, then
`launchctl load` it):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.example.ytfeed-pages</string>
  <key>ProgramArguments</key><array><string>/path/to/ytfeed/tools/publish_pages.sh</string></array>
  <key>StartInterval</key><integer>900</integer>
</dict></plist>
```

## Operations

- Logs: `docker logs -f ytfeed` (every sync, every provider failure — no silent errors).
- The scheduler is an internal loop (`playlist.poll_interval_seconds`, default hourly).
  Stopping the container just freezes the feed; readers tolerate that and it resumes on start.
- A video is blacklisted (never retried) **only** when it has no usable captions.
  LLM/API failures are retried next cycle — a provider outage can't silently eat videos.
- **yt-dlp is pinned** in `requirements.txt`. YouTube breaks it regularly: if `/status`
  shows playlist or subtitle errors, bump the pin to the latest release and
  `docker compose up -d --build`.

## Changelog

- **2.1 / 2026-10-20** — Feed caps raised (`max_items` per feed, default configurable),
  `tools/rebuild_feed.py` to regenerate a feed from the article archive,
  `tools/publish_pages.sh` for the GitHub Pages mirror.
- **2026-10-07** — LLM providers are plain OpenAI-compatible endpoints: a local gateway
  (LiteLLM) or a provider directly. Example config uses `api_base` / `model` / `api_key: ${VAR}`.
- **2026-09-08** — Multi-source support: `sources:` list, per-source feed, ledger, archive,
  route and prompt; one scheduler loop with per-source clocks; `prompts/tldr.md`.
- **2.0 / 2026-08-29** — Full rewrite as the dockerized `ytfeed` package.

## License

MIT
