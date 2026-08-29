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


def validate(cfg):
    if not cfg.get("playlist", {}).get("url"):
        raise ConfigError("playlist.url is required")
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
