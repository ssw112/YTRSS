"""LLM article generation with provider fallback chain + language verification."""
import os
import litellm

from .transcript import LANG_NAMES

try:
    from langdetect import detect as _langdetect
except ImportError:  # optional dependency; verification is skipped without it
    _langdetect = None

# Languages kept in the original; everything else is translated to English.
KEEP_LANGS = {"uk", "ru", "en", "es"}


def _language_rule(lang_code):
    if lang_code in KEEP_LANGS:
        name = LANG_NAMES.get(lang_code, lang_code)
        return (f"Write the ENTIRE article in {name} ({lang_code}). This is not "
                f"negotiable -- the video's spoken language is {name}. Do not "
                f"translate into any other language."), lang_code
    if lang_code:
        name = LANG_NAMES.get(lang_code, lang_code)
        return (f"The video's spoken language is {name} ({lang_code}). Translate "
                f"and write the ENTIRE article in English (en)."), "en"
    return ("Write the article in the transcript's own language if it is "
            "Ukrainian, Russian, English or Spanish; otherwise write it in "
            "English."), None


def _verify_language(html, expected, log):
    """Cheap post-generation check (no LLM call). Returns True if OK/unknown."""
    if not expected or _langdetect is None:
        return True
    import re
    text = re.sub(r"<[^>]+>", " ", html)[:800]
    try:
        got = _langdetect(text)
    except Exception:
        return True
    if got != expected:
        log.warning("Language check failed: expected %s, detected %s", expected, got)
        return False
    return True


def load_prompt_template(prompt_path):
    with open(prompt_path, encoding="utf-8") as f:
        return f.read()


def generate_article(cfg, title, transcript, video_id, lang_code, log, state=None):
    """Runs the provider chain. Returns HTML or None (transient failure).

    Never publishes a wrong-language article: on a language-check failure the
    same provider gets one forceful retry, then the next provider is tried.
    """
    prompt_path = cfg["llm"].get("prompt_path", "prompts/summarize.md")
    template = load_prompt_template(prompt_path)
    language_rule, expected_lang = _language_rule(lang_code)
    prompt = template.format(title=title, video_id=video_id,
                             language_rule=language_rule, transcript=transcript)

    for provider in cfg["llm"]["providers"]:
        label = provider["label"]
        for attempt in (1, 2):
            try:
                messages = [{"role": "user", "content": prompt}]
                if attempt == 2:
                    messages.append({"role": "user", "content":
                        f"Your previous draft was in the WRONG LANGUAGE. Rewrite the "
                        f"entire article strictly in "
                        f"{LANG_NAMES.get(expected_lang, expected_lang)} ({expected_lang})."})
                response = litellm.completion(
                    model=f"openai/{provider['model']}",
                    api_base=provider["api_base"],
                    api_key=provider["api_key"],
                    custom_llm_provider="openai",
                    messages=messages,
                    temperature=0.2,
                )
                content = (response.choices[0].message.content or "").strip()
                if not content:
                    log.warning("%s returned empty content.", label)
                    break  # empty output is a model problem, not a language one
                if not _verify_language(content, expected_lang, log):
                    if attempt == 1:
                        log.info("%s: retrying with forceful language correction.", label)
                        continue
                    log.warning("%s: wrong language twice, escalating to next provider.", label)
                    break

                try:
                    u = response.usage
                    content += (f'<hr/><p style="font-size:11px;color:#888;text-align:right;">'
                                f'<em>⚡ Summarized by {label} • Input: {u.prompt_tokens:,} '
                                f'tokens • Output: {u.completion_tokens:,} tokens</em></p>')
                except Exception:
                    pass
                if state is not None:
                    state.provider_ok(label)
                return content
            except Exception as e:
                log.warning("Provider '%s' failed: %s", label, str(e)[:300])
                if state is not None:
                    state.provider_fail(label, str(e)[:300])
                break  # API error -> next provider, don't burn the retry

    log.error("All providers failed; no summary generated.")
    return None


def test_provider(provider):
    """Live one-token completion -- the ONLY valid way to test a key/model
    (a /models listing can be public and prove nothing)."""
    try:
        r = litellm.completion(
            model=f"openai/{provider['model']}",
            api_base=provider["api_base"],
            api_key=provider["api_key"],
            custom_llm_provider="openai",
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=10,
        )
        content = (r.choices[0].message.content or "").strip()
        return (True, content) if content else (False, "empty completion")
    except Exception as e:
        return False, str(e)[:300]
