#!/usr/bin/env python3
"""Rebuild a ytfeed RSS file from the permanent article archive.

Usage (from the repo root):
    python3 tools/rebuild_feed.py SOURCE_NAME [--config PATH] [--dry-run]
    (SOURCE_NAME is "main" or a name from sources:)

Newest first by archive mtime, capped at the source's configured max_items,
written atomically (tmp + rename). Items that already exist in the current
feed keep their guid/pubDate; others get them from the archive mtime (same
scheme as feed.add_article: guid yt-summary-/yt-<name>-<epoch>).
Needs only PyYAML (already required by ytfeed). Reads config.yml raw, so no
API keys / env vars are needed. Default config: ./data/config.yml.
"""
import argparse
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import yaml
from ytfeed import feed as feed_mod
from ytfeed.config import sources

DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "config.yml")
MARK = " | https://www.youtube.com/watch?v="


def read_archive(path):
    with open(path, encoding="utf-8") as f:
        first = f.readline()
        body = f.read()
    title = first[len("<!--"):].rsplit(MARK, 1)[0].strip()
    return title, body


def build(cfg, src, data_dir):
    cfg = dict(cfg, data_dir=data_dir)
    feed_path = feed_mod._feed_path(cfg, src)
    arch = feed_mod._archive_dir(cfg, src)
    existing = {}
    if os.path.exists(feed_path):
        for it in ET.parse(feed_path).getroot().findall(".//item"):
            vid = it.find("link").text.rsplit("/", 1)[-1]
            existing[vid] = (it.find("guid").text, it.find("pubDate").text)

    files = [os.path.join(arch, n) for n in os.listdir(arch) if n.endswith(".html")]
    files.sort(key=lambda p: (os.path.getmtime(p), p), reverse=True)
    files = files[:src["max_items"]]

    # Skeleton via the package's own init_feed (into a scratch data dir)
    tmpd = tempfile.mkdtemp(prefix="rebuild_")
    scratch = dict(cfg, data_dir=tmpd)
    feed_mod.init_feed(scratch, src)
    tree = ET.parse(feed_mod._feed_path(scratch, src))
    channel = tree.getroot().find("channel")
    if os.path.exists(feed_path):  # keep the live channel header (may be hand-edited)
        live = ET.parse(feed_path).getroot().find("channel")
        for c in list(channel):
            channel.remove(c)
        for c in live:
            if c.tag != "item":
                channel.append(c)
    base = cfg["feed"]["public_base_url"].rstrip("/")
    tag = "yt-summary" if src["name"] == "main" else f"yt-{src['name']}"
    for p in files:
        vid = os.path.basename(p)[:-5]
        title, html = read_archive(p)
        ts = int(os.path.getmtime(p))
        guid, pub = existing.get(vid, (
            f"{tag}-{ts}",
            datetime.fromtimestamp(ts, timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")))
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "link").text = f"{base}/{src['route']}/{vid}"
        ET.SubElement(item, "guid", isPermaLink="false").text = guid
        ET.SubElement(item, "pubDate").text = pub
        ET.SubElement(item, "description").text = html
    ET.indent(tree, space="  ")
    return tree, feed_path, len(files)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    with open(a.config) as f:
        cfg = yaml.safe_load(f)
    data_dir = os.path.dirname(os.path.abspath(a.config))
    srcs = {s["name"]: s for s in sources(cfg)}
    if a.source not in srcs:
        sys.exit(f"unknown source {a.source}; have {list(srcs)}")
    tree, path, n = build(cfg, srcs[a.source], data_dir)
    if a.dry_run:
        print(f"{a.source}: would write {n} items to {path}")
        return
    tmp = path + ".tmp"
    tree.write(tmp, encoding="utf-8", xml_declaration=True)
    os.replace(tmp, path)
    print(f"{a.source}: wrote {n} items to {path}")


if __name__ == "__main__":
    main()
