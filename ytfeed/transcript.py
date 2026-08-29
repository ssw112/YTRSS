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

LANG_NAMES = {"uk": "Ukrainian", "ru": "Russian", "en": "English", "es": "Spanish",
              "de": "German", "fr": "French", "it": "Italian", "pl": "Polish",
              "pt": "Portuguese", "ja": "Japanese", "ko": "Korean", "zh": "Chinese"}


def video_metadata(video_id):
    """--dump-json goes to stdout only; nothing is written to disk."""
    cmd = [YT_DLP, "--dump-json", "--skip-download",
           f"https://www.youtube.com/watch?v={video_id}"]
    out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, timeout=120)
    return json.loads(out)


def detect_original_language(meta):
    """Returns (track, lang_code); either may be None."""
    autos = meta.get("automatic_captions") or {}
    subs = meta.get("subtitles") or {}
    orig_lang = meta.get("language")

    orig_tracks = [k for k in autos if k.endswith("-orig")]
    if orig_tracks:
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
        candidates = [track] + ([track[:-5]] if track.endswith("-orig") else [])
    else:
        log.warning("No -orig track / declared language; legacy fallback list.")
        candidates = ["uk-orig", "ru-orig", "en-orig", "es-orig", "en", "uk", "ru", "es"]

    with tempfile.TemporaryDirectory(prefix="ytfeed_") as tmp:
        tpl = os.path.join(tmp, video_id)
        for lang in candidates:
            cmd = [YT_DLP, "--write-auto-subs", "--sub-lang", lang,
                   "--skip-download", "--convert-subs", "srt", "-o", tpl,
                   f"https://www.youtube.com/watch?v={video_id}"]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
            srt = f"{tpl}.{lang}.srt"
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
