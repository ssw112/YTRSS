import os
import xml.etree.ElementTree as ET
from datetime import datetime

FEED_PATH = os.environ.get("FEED_PATH", "feed.xml")

def init_feed():
    """Initializes a blank RSS feed if it doesn't exist."""
    if os.path.exists(FEED_PATH):
        return

    os.makedirs(os.path.dirname(FEED_PATH) if os.path.dirname(FEED_PATH) else ".", exist_ok=True)
    
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    
    # Metadata
    ET.SubElement(channel, "title").text = os.environ.get("FEED_TITLE", "My Personal YouTube Read-Later Feed")
    ET.SubElement(channel, "link").text = os.environ.get("FEED_LINK", "http://localhost:8090/feed")
    ET.SubElement(channel, "description").text = "Summaries of longer YouTube videos and podcasts."
    ET.SubElement(channel, "language").text = "en"
    
    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ", level=0)
    tree.write(FEED_PATH, encoding="utf-8", xml_declaration=True)
    print(f"Created new blank RSS feed at: {FEED_PATH}")

def add_article_to_feed(title, link, html_content):
    """Appends a new article to the feed.xml file."""
    init_feed()
    
    # Parse the existing feed
    ET.register_namespace("", "") # Prevents ns0 prefixing
    tree = ET.parse(FEED_PATH)
    root = tree.getroot()
    channel = root.find("channel")
    
    # Create the new item
    item = ET.Element("item")
    
    ET.SubElement(item, "title").text = title
    ET.SubElement(item, "link").text = link
    
    # guid acts as the unique identifier for RSS readers to detect a new post
    guid = ET.SubElement(item, "guid", isPermaLink="false")
    guid.text = f"yt-summary-{int(datetime.now().timestamp())}"
    
    # PubDate in RFC 822 format (standard for RSS)
    pub_date = ET.SubElement(item, "pubDate")
    pub_date.text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    # Full article body inside description
    description = ET.SubElement(item, "description")
    description.text = html_content
    
    # Insert new item at the top of the feed (position after the metadata elements)
    channel.insert(4, item)
    
    # Limit feed to 20 items to prevent file bloating
    items = channel.findall("item")
    if len(items) > 20:
        for old_item in items[20:]:
            channel.remove(old_item)
            
    # Save the updated feed
    ET.indent(tree, space="  ", level=0)
    tree.write(FEED_PATH, encoding="utf-8", xml_declaration=True)
    print(f"Successfully appended '{title}' to {FEED_PATH}!")
