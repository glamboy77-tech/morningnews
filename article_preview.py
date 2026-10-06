"""Safe, short RSS article previews and opt-in publisher images."""

import html
import os
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit


class _RSSMarkup(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.images = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style"):
            self.hidden += 1
        if tag == "img" and attrs.get("src"):
            self.images.append(attrs["src"])
        if tag in ("p", "div", "br", "tr", "li"):
            self.text.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.hidden:
            self.hidden -= 1
        if tag in ("p", "div", "tr", "li"):
            self.text.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)


def rss_preview(description, title="", limit=145):
    """Extract a feed excerpt, never treating RSS markup as trusted HTML."""
    parser = _RSSMarkup()
    parser.feed(str(description or ""))
    text = re.sub(r"\s+", " ", html.unescape("".join(parser.text))).strip()
    text = re.sub(r"^(?:\[[^]]+\]\s*)?\(?(?:서울|세종)=연합뉴스\)?\s*", "", text)
    title_text = re.sub(r"\s+", " ", html.unescape(str(title or ""))).strip()
    if not text or text == title_text or len(text) < 35:
        return ""
    if len(text) > limit:
        excerpt = text[:limit]
        text = (excerpt.rsplit(" ", 1)[0] if " " in excerpt else excerpt).rstrip(" ,.;") + "…"
    return text


def rss_image_url(entry):
    """Extract an image candidate from feed metadata (no article-page scraping)."""
    candidates = []
    for key in ("media_thumbnail", "media_content", "enclosures", "links"):
        for media in entry.get(key, []) or []:
            if not isinstance(media, dict):
                continue
            url = media.get("url") or media.get("href")
            media_type = media.get("type", "")
            if url and (media_type.startswith("image/") or
                        (key in ("media_thumbnail", "media_content") and not media_type)):
                candidates.append(url)
    parser = _RSSMarkup()
    parser.feed(str(entry.get("description") or entry.get("summary") or ""))
    candidates.extend(parser.images)
    for candidate in candidates:
        candidate = html.unescape(str(candidate).strip())
        parts = urlsplit(candidate)
        if (parts.scheme == "https" and parts.hostname and not parts.username and not parts.password
                and re.search(r"\.(?:jpe?g|png|webp)$", parts.path, re.I)):
            return candidate
    return ""


def permitted_image(item):
    """Images are off until the publisher/source AND its image host are explicitly approved."""
    source = str(item.get("source", ""))
    allowed_sources = {name.strip() for name in os.getenv("MORNINGNEWS_IMAGE_SOURCES", "").split(",") if name.strip()}
    allowed_hosts = {name.strip().lower() for name in os.getenv("MORNINGNEWS_IMAGE_HOSTS", "").split(",") if name.strip()}
    if source not in allowed_sources:
        return ""
    candidate = item.get("image_url") or rss_image_url(item)
    if not isinstance(candidate, str):
        return ""
    candidate = html.unescape(candidate.strip())
    if any(ch in candidate for ch in "\r\n\t"):
        return ""
    try:
        parts = urlsplit(candidate)
        if (parts.scheme != "https" or parts.hostname not in allowed_hosts
                or parts.username or parts.password or parts.port not in (None, 443)
                or not re.search(r"\.(?:jpe?g|png|webp)$", parts.path, re.I)):
            return ""
    except ValueError:
        return ""
    return candidate