"""Internal sync loop -- replaces macOS cron/Hermes entirely."""
import time

from . import feed as feed_mod
from .playlist import fetch_playlist_ids
from .summarize import generate_article
from .transcript import download_transcript


def run_sync(app):
    """One sync pass. Processes at most one new video (rate friendliness)."""
    cfg, log, state = app.cfg, app.log, app.state
    ledger = feed_mod.load_ledger(cfg)
    try:
        playlist_ids = fetch_playlist_ids(cfg["playlist"]["url"])
    except Exception as e:
        log.error("Playlist fetch failed: %s", e)
        state.run_finished(f"error: playlist fetch: {str(e)[:200]}")
        return

    new_ids = [v for v in playlist_ids if v not in ledger]
    log.info("Playlist: %d videos, %d new.", len(playlist_ids), len(new_ids))
    if not new_ids:
        state.run_finished("nothing_new")
        return

    for video_id in new_ids:
        log.info("Processing %s", video_id)
        try:
            transcript, lang_code, title = download_transcript(video_id, log)
        except Exception as e:
            log.error("Metadata/subtitle fetch failed for %s: %s", video_id, e)
            state.run_finished(f"error: yt-dlp: {str(e)[:200]}")
            return  # transient (network/YouTube) -- retry next cycle

        if not transcript or len(transcript) < 100:
            # PERMANENT: no usable captions. Blacklist so we don't retry forever.
            log.warning("%s has no usable transcript -- blacklisting.", video_id)
            ledger.add(video_id)
            feed_mod.save_ledger(cfg, ledger)
            continue

        html = generate_article(cfg, title, transcript, video_id, lang_code,
                                log, state)
        if html is None:
            # TRANSIENT: all LLM providers failed. Never blacklist; stop the
            # run (systemic outage -- the next cycle retries).
            log.error("LLM chain exhausted for %s; will retry next cycle.", video_id)
            state.run_finished("error: all LLM providers failed")
            return

        feed_mod.add_article(cfg, f"AI Article: {title}", video_id, html)
        feed_mod.archive_article(cfg, f"AI Article: {title}", video_id, html)
        ledger.add(video_id)
        feed_mod.save_ledger(cfg, ledger)
        state.article_published(title)
        log.info("Published: %s", title)
        break  # one article per cycle

    state.run_finished("ok")


def loop(app):
    while True:
        if app.cfg is None:
            app.log.info("No config yet -- waiting for /setup.")
        else:
            try:
                run_sync(app)
            except Exception as e:
                app.log.exception("Unhandled error in sync run: %s", e)
                app.state.run_finished(f"error: crash: {str(e)[:200]}")
        interval = 3600
        if app.cfg is not None:
            interval = int(app.cfg["playlist"].get("poll_interval_seconds", 3600))
        time.sleep(interval if app.cfg is not None else 30)
