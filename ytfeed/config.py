"""Config loading for ytfeed.

config.yml is the single source of truth; API keys are referenced as
${ENV_VAR} so secrets never live in the file itself.
"""
import os
import re
import yaml

DEFAULT_CONFIG_PATH = os.environ.get("YTFEED_CONFIG", "/data/config.yml")

_ENV_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")


class ConfigError(Exception):
    pass


def _interpolate(value):
    if isinstance(value, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _interpolate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v) for v in value]
    return value


def load_config(path=None):
    """Returns the parsed config dict, or None if the file doesn't exist yet
    (first boot -> server runs in setup-only mode)."""
    path = path or DEFAULT_CONFIG_PATH
    if not os.path.exists(path):
        return None
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    cfg = _interpolate(raw)
    validate(cfg)
    return cfg


def sources(cfg):
    """Normalized list of sources. The legacy top-level `playlist:` block is
    always the implicit "main" source (feed.xml, processed_videos.json,
    articles/, /article/{id}) so existing feeds keep working unchanged.
    Extra sources come from `sources:` and get their own feed/ledger/archive/
    prompt/route derived from their name."""
    out = []
    pl = cfg.get("playlist") or {}
    if pl.get("url"):
        out.append({
            "name": "main",
            "url": pl["url"],
            "poll_interval_seconds": int(pl.get("poll_interval_seconds", 3600)),
            "prompt_path": cfg.get("llm", {}).get("prompt_path", "prompts/summarize.md"),
            "feed_file": "feed.xml",
            "ledger_file": "processed_videos.json",
            "archive_subdir": "",
            "route": "article",
            "title_prefix": "AI Article: ",
            "feed_title": cfg.get("feed", {}).get("title", "ytfeed"),
            "feed_description": cfg.get("feed", {}).get("description", "AI summaries of YouTube videos."),
            "max_items": int(cfg.get("feed", {}).get("max_items", 20)),
        })
    for src in cfg.get("sources") or []:
        name = src["name"]
        out.append({
            "name": name,
            "url": src["url"],
            "poll_interval_seconds": int(src.get("poll_interval_seconds", 600)),
            "prompt_path": src.get("prompt_path", f"/app/prompts/{name}.md"),
            "feed_file": src.get("feed_file", f"{name}.xml"),
            "ledger_file": src.get("ledger_file", f"processed_{name}.json"),
            "archive_subdir": src.get("archive_subdir", name),
            "route": src.get("route", name),
            "title_prefix": src.get("title_prefix", ""),
            "feed_title": src.get("feed_title", name),
            "feed_description": src.get("feed_description", ""),
            "max_items": int(src.get("max_items", cfg.get("feed", {}).get("max_items", 20))),
        })
    return out


def validate(cfg):
    if not cfg.get("playlist", {}).get("url") and not cfg.get("sources"):
        raise ConfigError("playlist.url or sources[] is required")
    names = set()
    for src in cfg.get("sources") or []:
        for field in ("name", "url"):
            if not src.get(field):
                raise ConfigError(f"source missing '{field}'")
        if src["name"] in names or src["name"] in ("main", "article", "feed"):
            raise ConfigError(f"duplicate/reserved source name '{src['name']}'")
        names.add(src["name"])
    providers = cfg.get("llm", {}).get("providers") or []
    if not providers:
        raise ConfigError("llm.providers must have at least one entry")
    for p in providers:
        for field in ("label", "model", "api_base", "api_key"):
            if not p.get(field):
                raise ConfigError(f"llm provider '{p.get('label', '?')}' missing '{field}'")
    if not cfg.get("feed", {}).get("public_base_url"):
        raise ConfigError("feed.public_base_url is required")


def data_dir(cfg):
    return (cfg or {}).get("data_dir") or os.environ.get("YTFEED_DATA", "/data")
