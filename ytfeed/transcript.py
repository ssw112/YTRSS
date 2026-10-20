"""Original-language subtitle download + SRT cleaning.

Language selection is metadata-driven, never a fixed priority list: YouTube
serves auto-TRANSLATED captions in every language, so guessing feeds the LLM
a machine translation. The '*-orig' auto-caption track is the authoritative
marker of the true spoken language.
"""
import json
import os
import re
import subprocess
import tempfile

YT_DLP = "yt-dlp"


class PermanentFailure(Exception):
    """Raised when a video can never be summarized (private/removed/etc)."""

LANG_NAMES = {"uk": "Ukrainian", "ru": "Russian", "en": "English", "es": "Spanish",
              "de": "German", "fr": "French", "it": "Italian", "pl": "Polish",
              "pt": "Portuguese", "ja": "Japanese", "ko": "Korean", "zh": "Chinese"}


PERMANENT_MARKERS = (
    "private video",
    "video unavailable",
    "has been removed",
    "this video is not available",
    "video is unavailable",
    "account associated with this video has been terminated",
    "no longer available",
)


def video_metadata(video_id):
    """--dump-json goes to stdout only; nothing is written to disk."""
    cmd = [YT_DLP, "--dump-json", "--skip-download",
           f"https://www.youtube.com/watch?v={video_id}"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        stderr_lower = (proc.stderr or "").lower()
        if "private video" in stderr_lower:
            raise PermanentFailure("Video is private.")
        if "video unavailable" in stderr_lower or "this video is not available" in stderr_lower \
                or "video is unavailable" in stderr_lower:
            raise PermanentFailure("Video is unavailable.")
        if "has been removed" in stderr_lower or "no longer available" in stderr_lower:
            raise PermanentFailure("Video has been removed.")
        if "account associated with this video has been terminated" in stderr_lower:
            raise PermanentFailure("The account associated with this video has been terminated.")
        raise RuntimeError((proc.stderr or "")[:300])
    return json.loads(proc.stdout)


def detect_original_language(meta):
    """Returns (track, lang_code); either may be None."""
    autos = meta.get("automatic_captions") or {}
    subs = meta.get("subtitles") or {}
    orig_lang = meta.get("language")

    orig_tracks = [k for k in autos if k.endswith("-orig")]
    if orig_tracks:
        # Auto-dubbed videos expose several -orig tracks (e.g. en-US-orig for the
        # dub + uk-orig for the real audio). Prefer the one matching the video's
        # declared language; never blindly take the first.
        if orig_lang:
            for k in orig_tracks:
                if k[:-5] == orig_lang or k[:-5].split("-")[0] == orig_lang.split("-")[0]:
                    return k, orig_lang
        track = orig_tracks[0]
        return track, track[:-5]
    if orig_lang and (orig_lang in subs or orig_lang in autos):
        return orig_lang, orig_lang
    return None, orig_lang


def download_transcript(video_id, log):
    """Returns (clean_text, lang_code, title) or raises PermanentFailure."""
    meta = video_metadata(video_id)
    title = meta.get("title") or f"YouTube Video ({video_id})"
    track, lang_code = detect_original_language(meta)

    if track:
        log.info("Detected original language: %s (track %s)", lang_code, track)
        autos = meta.get("automatic_captions") or {}
        others = [k for k in autos if k.endswith("-orig") and k != track]
        candidates = [track] + ([track[:-5]] if track.endswith("-orig") else []) + others
    else:
        log.warning("No -orig track / declared language; legacy fallback list.")
        candidates = ["uk-orig", "ru-orig", "en-orig", "es-orig", "en", "uk", "ru", "es"]

    with tempfile.TemporaryDirectory(prefix="ytfeed_") as tmp:
        tpl = os.path.join(tmp, video_id)
        for lang in candidates:
            cmd = [YT_DLP, "--write-auto-subs", "--sub-lang", lang,
                   "--skip-download", "--convert-subs", "srt", "-o", tpl,
                   f"https://www.youtube.com/watch?v={video_id}"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            srt = f"{tpl}.{lang}.srt"
            if not os.path.exists(srt) and proc.returncode != 0:
                # yt-dlp itself failed (network/throttle/HTTP error): TRANSIENT.
                # Never turn this into a "no captions" stub; retry next cycle.
                err = (proc.stderr or "").strip().splitlines()
                raise RuntimeError(f"subtitle download failed for {lang}: {err[-1][:200] if err else 'unknown'}")
            if os.path.exists(srt):
                log.info("Downloaded %s subtitles.", lang)
                if lang_code is None:
                    lang_code = lang[:-5] if lang.endswith("-orig") else lang
                return clean_srt(srt), lang_code, title

    return None, lang_code, title


def clean_srt(srt_path):
    """SRT -> deduplicated plain text (YouTube auto-caption rolling windows
    repeat each line 2-3 times)."""
    with open(srt_path, encoding="utf-8", errors="ignore") as f:
        raw = f.read()

    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.isdigit() or "-->" in line:
            continue
        line = re.sub(r"<[^>]+>", "", line)  # strip inline timing tags
        if line and (not lines or line != lines[-1]):
            lines.append(line)

    # Second pass: drop lines fully contained in the following line (rolling window)
    out = []
    for i, line in enumerate(lines):
        if i + 1 < len(lines) and line in lines[i + 1]:
            continue
        out.append(line)
    return " ".join(out)
