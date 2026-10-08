"""Conservative, display-only grouping of reports about the same event."""

import re
from datetime import datetime
from difflib import SequenceMatcher

from rss_manager import canonical_link_for_dedupe, normalize_title_for_dedupe


def _same_event(left, right):
    first = normalize_title_for_dedupe(left.get('title', ''))
    second = normalize_title_for_dedupe(right.get('title', ''))
    if not first or not second:
        return False
    left_time = left.get('published_dt')
    right_time = right.get('published_dt')
    if isinstance(left_time, datetime) and isinstance(right_time, datetime):
        if abs((left_time - right_time).total_seconds()) > 36 * 3600:
            return False
    if first == second:
        return True
    if min(len(first), len(second)) < 16:
        return False
    # Different figures often mean a subsequent development, not another report.
    if set(re.findall(r'\d+', first)) != set(re.findall(r'\d+', second)):
        return False
    tokens_a, tokens_b = set(first.split()), set(second.split())
    if len(tokens_a & tokens_b) < 3:
        return False
    # A one-word substitution may change the place, actor, or outcome entirely.
    if not (tokens_a <= tokens_b or tokens_b <= tokens_a):
        return False
    return SequenceMatcher(None, first, second).ratio() >= 0.86


def group_articles(items):
    """Return new representative dictionaries, retaining all grouped source links."""
    groups = []
    for item in items:
        link = item.get('link', '')
        canonical = canonical_link_for_dedupe(link)
        match = next((group for group in groups if
                      (canonical and canonical == canonical_link_for_dedupe(group.get('link', '')))
                      or _same_event(group, item)), None)
        if match is None:
            groups.append({**item, 'related_full_sources': list(item.get('related_full_sources') or [])})
            continue
        related = match['related_full_sources']
        if link and link != match.get('link') and not any(entry.get('link') == link for entry in related):
            related.append({'link': link, 'title': item.get('title', ''),
                            'source': item.get('source', '')})
        for entry in item.get('related_full_sources') or []:
            if entry.get('link') and entry['link'] != match.get('link') and not any(
                    previous.get('link') == entry['link'] for previous in related):
                related.append(entry)
    return groups