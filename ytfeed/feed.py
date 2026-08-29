"""RSS feed building with a size cap, plus the processed-videos ledger."""
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


def _feed_path(cfg):
    from .config import data_dir
    return os.path.join(data_dir(cfg), "feed.xml")


def _ledger_path(cfg):
    from .config import data_dir
    return os.path.join(data_dir(cfg), "processed_videos.json")


def init_feed(cfg):
    path = _feed_path(cfg)
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = cfg["feed"].get("title", "ytfeed")
    ET.SubElement(channel, "link").text = cfg["feed"]["public_base_url"]
    ET.SubElement(channel, "description").text = cfg["feed"].get(
        "description", "AI summaries of YouTube videos.")
    ET.SubElement(channel, "language").text = "en"
    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def add_article(cfg, title, video_id, html_content):
    init_feed(cfg)
    path = _feed_path(cfg)
    ET.register_namespace("", "")
    tree = ET.parse(path)
    channel = tree.getroot().find("channel")

    item = ET.Element("item")
    ET.SubElement(item, "title").text = title
    # Dummy article link (never a youtube.com URL: Feedly mobile would treat
    # the entry as a video bookmark and kick to the YouTube app).
    base = cfg["feed"]["public_base_url"].rstrip("/")
    ET.SubElement(item, "link").text = f"{base}/article/{video_id}"
    guid = ET.SubElement(item, "guid", isPermaLink="false")
    now = datetime.now(timezone.utc)
    guid.text = f"yt-summary-{int(now.timestamp())}"
    ET.SubElement(item, "pubDate").text = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    ET.SubElement(item, "description").text = html_content

    channel.insert(4, item)
    max_items = int(cfg["feed"].get("max_items", 20))
    for old in channel.findall("item")[max_items:]:
        channel.remove(old)

    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _archive_dir(cfg):
    from .config import data_dir
    return os.path.join(data_dir(cfg), "articles")


def archive_article(cfg, title, video_id, html_content):
    """Permanent per-article copy: survives feed rotation (max_items), keeps
    /article/{id} links alive forever, and is grep/Spotlight-searchable."""
    path = os.path.join(_archive_dir(cfg), f"{video_id}.html")
    os.makedirs(_archive_dir(cfg), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"<!-- {title} | https://www.youtube.com/watch?v={video_id} -->\n")
        f.write(html_content)


def get_article(cfg, video_id):
    """Returns (title, html) for a video id, or (None, None).
    Looks in the live feed first, then the permanent archive."""
    if not video_id or not video_id.replace("-", "").replace("_", "").isalnum():
        return None, None
    path = _feed_path(cfg)
    if os.path.exists(path):
        tree = ET.parse(path)
        suffix = f"/article/{video_id}"
        for item in tree.getroot().findall(".//item"):
            link = item.find("link")
            if link is not None and (link.text or "").endswith(suffix):
                title = item.find("title")
                desc = item.find("description")
                return (title.text if title is not None else video_id,
                        desc.text if desc is not None else None)
    archived = os.path.join(_archive_dir(cfg), f"{video_id}.html")
    if os.path.exists(archived):
        with open(archived, encoding="utf-8") as f:
            first = f.readline()
            title = first.split("|")[0].replace("<!--", "").strip() or video_id
            return title, f.read()
    return None, None


def load_ledger(cfg):
    path = _ledger_path(cfg)
    if os.path.exists(path):
        try:
            with open(path) as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_ledger(cfg, ids):
    path = _ledger_path(cfg)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(sorted(ids), f, indent=2)
