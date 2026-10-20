"""RSS feed building with a size cap, plus the processed-videos ledger."""
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


def _main(cfg):
    from .config import sources
    return sources(cfg)[0]


def _src(cfg, src):
    return src or _main(cfg)


def _feed_path(cfg, src=None):
    from .config import data_dir
    return os.path.join(data_dir(cfg), _src(cfg, src)["feed_file"])


def _ledger_path(cfg, src=None):
    from .config import data_dir
    return os.path.join(data_dir(cfg), _src(cfg, src)["ledger_file"])


def init_feed(cfg, src=None):
    src = _src(cfg, src)
    path = _feed_path(cfg, src)
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = src["feed_title"]
    ET.SubElement(channel, "link").text = cfg["feed"]["public_base_url"]
    ET.SubElement(channel, "description").text = src["feed_description"]
    ET.SubElement(channel, "language").text = "en"
    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def add_article(cfg, title, video_id, html_content, src=None):
    src = _src(cfg, src)
    init_feed(cfg, src)
    path = _feed_path(cfg, src)
    ET.register_namespace("", "")
    tree = ET.parse(path)
    channel = tree.getroot().find("channel")

    item = ET.Element("item")
    ET.SubElement(item, "title").text = title
    # Dummy article link (never a youtube.com URL: Feedly mobile would treat
    # the entry as a video bookmark and kick to the YouTube app).
    base = cfg["feed"]["public_base_url"].rstrip("/")
    ET.SubElement(item, "link").text = f"{base}/{src['route']}/{video_id}"
    guid = ET.SubElement(item, "guid", isPermaLink="false")
    now = datetime.now(timezone.utc)
    tag = "yt-summary" if src["name"] == "main" else f"yt-{src['name']}"
    guid.text = f"{tag}-{int(now.timestamp())}"
    ET.SubElement(item, "pubDate").text = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    ET.SubElement(item, "description").text = html_content

    channel.insert(4, item)
    max_items = src["max_items"]
    for old in channel.findall("item")[max_items:]:
        channel.remove(old)

    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _archive_dir(cfg, src=None):
    from .config import data_dir
    return os.path.join(data_dir(cfg), "articles", _src(cfg, src)["archive_subdir"])


def archive_article(cfg, title, video_id, html_content, src=None):
    """Permanent per-article copy: survives feed rotation (max_items), keeps
    /article/{id} links alive forever, and is grep/Spotlight-searchable."""
    src = _src(cfg, src)
    path = os.path.join(_archive_dir(cfg, src), f"{video_id}.html")
    os.makedirs(_archive_dir(cfg, src), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"<!-- {title} | https://www.youtube.com/watch?v={video_id} -->\n")
        f.write(html_content)


def get_article(cfg, video_id, src=None):
    """Returns (title, html) for a video id, or (None, None).
    Looks in the live feed first, then the permanent archive."""
    src = _src(cfg, src)
    if not video_id or not video_id.replace("-", "").replace("_", "").isalnum():
        return None, None
    path = _feed_path(cfg, src)
    if os.path.exists(path):
        tree = ET.parse(path)
        suffix = f"/{src['route']}/{video_id}"
        for item in tree.getroot().findall(".//item"):
            link = item.find("link")
            if link is not None and (link.text or "").endswith(suffix):
                title = item.find("title")
                desc = item.find("description")
                return (title.text if title is not None else video_id,
                        desc.text if desc is not None else None)
    archived = os.path.join(_archive_dir(cfg, src), f"{video_id}.html")
    if os.path.exists(archived):
        with open(archived, encoding="utf-8") as f:
            first = f.readline()
            title = first.split("|")[0].replace("<!--", "").strip() or video_id
            return title, f.read()
    return None, None


def load_ledger(cfg, src=None):
    path = _ledger_path(cfg, src)
    if os.path.exists(path):
        try:
            with open(path) as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_ledger(cfg, ids, src=None):
    path = _ledger_path(cfg, src)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(sorted(ids), f, indent=2)
