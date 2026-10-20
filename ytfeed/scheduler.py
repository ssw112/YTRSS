"""Internal sync loop -- replaces macOS cron/Hermes entirely."""
import logging
import os
import time

from . import feed as feed_mod
from .config import sources
from .playlist import fetch_playlist_ids
from .summarize import generate_article
from .transcript import PermanentFailure, download_transcript


def _stub_html(video_id, reason):
    url = f"https://www.youtube.com/watch?v={video_id}"
    return (f'<p><strong>\u26a0\ufe0f This video could not be summarized.</strong></p>'
            f'<p>{reason}</p><hr/>'
            f'<p>\u25b6\ufe0f <a href="{url}">Watch on YouTube</a></p>')


def _publish_stub(cfg, state, log, ledger, video_id, title, reason, src):
    stub_title = f"\u26a0\ufe0f Not summarized: {title}"
    html = _stub_html(video_id, reason)
    feed_mod.add_article(cfg, stub_title, video_id, html, src)
    feed_mod.archive_article(cfg, stub_title, video_id, html, src)
    ledger.add(video_id)
    feed_mod.save_ledger(cfg, ledger, src)
    state.article_published(stub_title, src["name"])
    log.warning("[%s] Published stub for %s: %s", src["name"], video_id, reason)


def run_sync(app, src=None):
    """One sync pass for one source. Processes at most one new video."""
    cfg, log, state = app.cfg, app.log, app.state
    if src is None:
        src = sources(cfg)[0]
    name = src["name"]
    ledger = feed_mod.load_ledger(cfg, src)
    try:
        playlist_ids = fetch_playlist_ids(src["url"])
    except Exception as e:
        log.error("[%s] Playlist fetch failed: %s", name, e)
        state.run_finished(f"error: playlist fetch: {str(e)[:200]}", name)
        return

    new_ids = [v for v in playlist_ids if v not in ledger]
    log.info("[%s] Playlist: %d videos, %d new.", name, len(playlist_ids), len(new_ids))
    if not new_ids:
        state.run_finished("nothing_new", name)
        return

    for video_id in new_ids:
        log.info("[%s] Processing %s", name, video_id)
        try:
            transcript, lang_code, title = download_transcript(video_id, log)
        except PermanentFailure as e:
            _publish_stub(cfg, state, log, ledger, video_id,
                          title=f"YouTube Video ({video_id})", reason=str(e), src=src)
            continue
        except Exception as e:
            log.error("[%s] Metadata/subtitle fetch failed for %s: %s", name, video_id, e)
            state.run_finished(f"error: yt-dlp: {str(e)[:200]}", name)
            return  # transient (network/YouTube) -- retry next cycle

        if not transcript or len(transcript) < 100:
            # PERMANENT: no usable captions. Publish a stub so it's visible in Feedly.
            _publish_stub(cfg, state, log, ledger, video_id, title=title,
                          reason="No transcript available (no captions in any language).",
                          src=src)
            continue

        html = generate_article(cfg, title, transcript, video_id, lang_code,
                                log, state, prompt_path=src["prompt_path"])
        if html is None:
            # TRANSIENT: all LLM providers failed. Never blacklist; stop the
            # run (systemic outage -- the next cycle retries).
            log.error("[%s] LLM chain exhausted for %s; will retry next cycle.", name, video_id)
            state.run_finished("error: all LLM providers failed", name)
            return

        feed_title = f"{src['title_prefix']}{title}"
        feed_mod.add_article(cfg, feed_title, video_id, html, src)
        feed_mod.archive_article(cfg, feed_title, video_id, html, src)
        ledger.add(video_id)
        feed_mod.save_ledger(cfg, ledger, src)
        state.article_published(title, name)
        log.info("[%s] Published: %s", name, title)
        break  # one article per cycle per source

    state.run_finished("ok", name)


def loop(app):
    """Single loop, per-source clocks: each source runs on its own
    poll_interval_seconds (main hourly, tldr every 10 min, ...)."""
    next_run = {}
    while True:
        if app.cfg is None:
            app.log.info("No config yet -- waiting for /setup.")
            time.sleep(30)
            continue
        now = time.monotonic()
        for src in sources(app.cfg):
            if now < next_run.get(src["name"], 0):
                continue
            try:
                run_sync(app, src)
            except Exception as e:
                app.log.exception("[%s] Unhandled error in sync run: %s", src["name"], e)
                app.state.run_finished(f"error: crash: {str(e)[:200]}", src["name"])
            next_run[src["name"]] = time.monotonic() + src["poll_interval_seconds"]
            app.log.info("[%s] cycle done fd=%d", src["name"], len(os.listdir("/proc/self/fd")))
        time.sleep(30)
